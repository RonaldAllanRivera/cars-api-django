"""
The monthly cap on AI spend, and the ledger behind it.

Every call goes reserve -> call -> settle:

1. reserve() locks the month's BudgetPeriod row, refuses if the call's
   worst-case cost would cross the cap, and otherwise counts that worst case
   as already spent.
2. The provider is called outside any lock, so a slow response never holds
   up another request.
3. settle() replaces the reservation with what the call really cost.

A worker killed between reserve and settle leaves its reservation standing,
so a crash over-reports spend and can never let the cap be exceeded.
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.publishing.models import AiUsage, BudgetPeriod
from apps.publishing.services.pricing import Rates, rates_for

PER_MILLION = Decimal(1_000_000)
MICRO_DOLLAR = Decimal("0.000001")
# Chat formatting wraps the request in a few tokens the serialized body does not show.
FORMAT_OVERHEAD_TOKENS = 16
SETTLEABLE = (AiUsage.Status.RESERVED, AiUsage.Status.ABANDONED)


class BudgetExceededError(Exception):
    def __init__(self, *, spent_usd: Decimal, cap_usd: Decimal, estimate_usd: Decimal):
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        self.estimate_usd = estimate_usd
        super().__init__(
            f"Monthly AI budget of ${cap_usd:.2f} reached: ${spent_usd:.2f} spent, "
            f"and this call could cost up to ${estimate_usd:.4f}."
        )


def current_rates() -> Rates:
    """The configured model's prices; raises UnknownModelPriceError before anything can be spent."""
    return rates_for(settings.ANTHROPIC["model"])


def cap_usd() -> Decimal:
    """0 means no cap."""
    return _decimal(settings.AI_BUDGET["monthly_usd"])


def month_start(moment: datetime | None = None) -> date:
    return (moment or timezone.now()).astimezone(UTC).date().replace(day=1)


def compute_cost(
    *,
    input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    output_tokens: int = 0,
    rates: Rates,
) -> Decimal:
    """
    Each count at its own rate. The Messages API reports cache writes and reads
    beside input_tokens, never inside it, so nothing is subtracted.
    """
    cost = (
        max(input_tokens, 0) * rates.input
        + max(cache_creation_input_tokens, 0) * rates.cache_write
        + max(cache_read_input_tokens, 0) * rates.cache_read
        + max(output_tokens, 0) * rates.output
    ) / PER_MILLION
    return cost.quantize(MICRO_DOLLAR, rounding=ROUND_HALF_UP)


def estimate_usd(request: object, *, max_tokens: int, rates: Rates) -> Decimal:
    """
    An upper bound on what a call can cost, not a guess.

    A token always covers at least one byte, so the serialized request's UTF-8
    length is a ceiling on its input tokens. A characters-per-token average is
    not: emoji and accented text can undercount several times over. Input is
    priced at whichever is dearer, a plain read or a cache write, and output at
    the whole max_tokens allowance, which the API enforces.
    """
    prompt_bytes = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))
    input_rate = max(rates.input, rates.cache_write)
    cost = ((prompt_bytes + FORMAT_OVERHEAD_TOKENS) * input_rate + max_tokens * rates.output) / PER_MILLION
    return cost.quantize(MICRO_DOLLAR, rounding=ROUND_UP)


def reserve(*, blog_post, estimate_usd: Decimal, model: str, rates: Rates) -> AiUsage:
    """Count the worst case as spent, or raise BudgetExceededError before anything is sent."""
    now = timezone.now()
    month = month_start(now)
    # The lock below needs the row to exist; get_or_create tolerates a concurrent first insert.
    BudgetPeriod.objects.get_or_create(month=month)
    cap = cap_usd()

    with transaction.atomic():
        # Serialises every reservation for the month, so two requests cannot both read the
        # same total and both squeeze under the cap.
        period = BudgetPeriod.objects.select_for_update().get(month=month)
        if cap > 0 and period.spent_usd + estimate_usd > cap:
            raise BudgetExceededError(spent_usd=period.spent_usd, cap_usd=cap, estimate_usd=estimate_usd)

        usage = AiUsage.objects.create(
            blog_post=blog_post,
            model=model,
            status=AiUsage.Status.RESERVED,
            input_usd_per_1m=rates.input,
            output_usd_per_1m=rates.output,
            cache_write_usd_per_1m=rates.cache_write,
            cache_read_usd_per_1m=rates.cache_read,
            reserved_usd=estimate_usd,
            cost_usd=estimate_usd,
            occurred_at=now,
        )
        BudgetPeriod.objects.filter(pk=period.pk).update(
            spent_usd=F("spent_usd") + estimate_usd, calls=F("calls") + 1, updated_at=now
        )
    return usage


def settle(
    usage: AiUsage,
    *,
    succeeded: bool,
    input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    output_tokens: int = 0,
    request_id: str = "",
    stop_reason: str = "",
    latency_ms: int | None = None,
) -> AiUsage:
    """
    Replace the reservation with the real cost. A failed call is charged for
    whatever tokens it used, which is nothing when it never reached the model.
    """
    now = timezone.now()
    with transaction.atomic():
        locked = AiUsage.objects.select_for_update().get(pk=usage.pk)
        if locked.status not in SETTLEABLE:
            # Already settled: adjusting the period again would count the call twice.
            return locked

        # The rates in force when the call was reserved, not today's.
        rates = Rates(
            input=locked.input_usd_per_1m,
            output=locked.output_usd_per_1m,
            cache_write=locked.cache_write_usd_per_1m,
            cache_read=locked.cache_read_usd_per_1m,
        )
        counts = {
            "input_tokens": max(input_tokens, 0),
            "cache_creation_input_tokens": max(cache_creation_input_tokens, 0),
            "cache_read_input_tokens": max(cache_read_input_tokens, 0),
            "output_tokens": max(output_tokens, 0),
        }
        actual = compute_cost(**counts, rates=rates)
        # The month the call started in: one reserved at 23:59 on the 31st belongs to that month.
        month = month_start(locked.occurred_at)
        BudgetPeriod.objects.select_for_update().get(month=month)
        BudgetPeriod.objects.filter(month=month).update(
            spent_usd=F("spent_usd") - locked.cost_usd + actual, updated_at=now
        )

        locked.status = AiUsage.Status.SUCCEEDED if succeeded else AiUsage.Status.FAILED
        for field, count in counts.items():
            setattr(locked, field, count)
        locked.total_tokens = sum(counts.values())
        locked.cost_usd = actual
        locked.request_id = request_id[:64]
        locked.stop_reason = stop_reason[:32]
        locked.latency_ms = latency_ms
        locked.settled_at = now
        locked.save()
    return locked


def abandon(usage: AiUsage) -> AiUsage:
    """
    Close a call whose outcome is unknown, keeping its worst-case cost.

    For a request that may have been processed without the response arriving,
    such as a read timeout: the tokens may have been billed, so releasing the
    reservation could undercount spend.
    """
    now = timezone.now()
    AiUsage.objects.filter(pk=usage.pk, status=AiUsage.Status.RESERVED).update(
        status=AiUsage.Status.ABANDONED, settled_at=now
    )
    return AiUsage.objects.get(pk=usage.pk)


def reconcile_stale_reservations() -> int:
    """
    Mark reservations a killed worker never settled as abandoned. Their cost is
    kept, because the tokens were probably spent; a late settle still corrects it.
    """
    now = timezone.now()
    minutes = settings.AI_BUDGET["reservation_stale_minutes"]
    abandoned = AiUsage.objects.filter(
        status=AiUsage.Status.RESERVED, occurred_at__lt=now - timedelta(minutes=minutes)
    ).update(status=AiUsage.Status.ABANDONED, settled_at=now)

    if abandoned:
        error_logger.record(
            ErrorEvent.Context.AI_BUDGET,
            f"{abandoned} AI call(s) were never settled and are counted at their worst-case cost.",
            severity=ErrorEvent.Severity.WARNING,
            details={"abandoned": abandoned, "older_than_minutes": minutes},
        )
    return abandoned


def month_to_date() -> dict:
    """The dashboard and API shape. Reading never creates a period row."""
    month = month_start()
    period = BudgetPeriod.objects.filter(month=month).first()
    spent = period.spent_usd if period else Decimal("0")
    cap = cap_usd()

    summary = {
        "month": month,
        "spent_usd": spent,
        "calls": period.calls if period else 0,
        "cap_usd": None,
        "remaining_usd": None,
        "percent_used": None,
    }
    if cap > 0:
        summary.update(
            cap_usd=cap,
            # A cap lowered below what is already spent leaves nothing, not a negative.
            remaining_usd=max(cap - spent, Decimal("0")),
            percent_used=int((spent * 100 / cap).to_integral_value(rounding=ROUND_DOWN)),
        )
    return summary


def recompute_period(month: date) -> BudgetPeriod:
    """Rebuild a month's running total from its usage rows, which are the source of truth."""
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    end = datetime(month.year + month.month // 12, month.month % 12 + 1, 1, tzinfo=UTC)
    BudgetPeriod.objects.get_or_create(month=month)

    with transaction.atomic():
        period = BudgetPeriod.objects.select_for_update().get(month=month)
        totals = AiUsage.objects.filter(occurred_at__gte=start, occurred_at__lt=end).aggregate(
            spent=Sum("cost_usd"), calls=Count("pk")
        )
        period.spent_usd = totals["spent"] or Decimal("0")
        period.calls = totals["calls"]
        period.save(update_fields=["spent_usd", "calls", "updated_at"])
    return period


def _decimal(value) -> Decimal:
    # Through str: Decimal(0.15) carries the float's binary error into every total.
    return Decimal(str(value))
