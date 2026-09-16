import threading
import time
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.observability.models import ErrorEvent
from apps.publishing.models import AiUsage, BudgetPeriod
from apps.publishing.services import budget
from tests.factories import BlogPostFactory

pytestmark = pytest.mark.django_db

MODEL = "claude-haiku-4-5"


def reserve(estimate="0.01", post=None):
    return budget.reserve(blog_post=post, estimate_usd=Decimal(estimate), model=MODEL, rates=budget.current_rates())


def spent(month=None) -> Decimal:
    return BudgetPeriod.objects.get(month=month or budget.month_start()).spent_usd


class TestCost:
    def test_tokens_are_priced_per_million_at_each_rate(self):
        cost = budget.compute_cost(input_tokens=1_000_000, output_tokens=1_000_000, rates=budget.current_rates())

        assert cost == Decimal("6.000000")  # $1 in, $5 out on claude-haiku-4-5

    def test_cache_writes_and_reads_are_separate_counts_at_their_own_rates(self):
        """Anthropic reports cached tokens beside input_tokens, never inside it."""
        cost = budget.compute_cost(
            cache_creation_input_tokens=1_000_000, cache_read_input_tokens=1_000_000, rates=budget.current_rates()
        )

        assert cost == Decimal("1.350000")  # $1.25 per million written, $0.10 read

    def test_cost_is_an_exact_decimal_to_the_millionth_of_a_dollar(self):
        cost = budget.compute_cost(input_tokens=1234, output_tokens=567, rates=budget.current_rates())

        assert cost == Decimal("0.004069")
        assert isinstance(cost, Decimal)

    def test_rates_follow_the_configured_model(self, settings):
        settings.ANTHROPIC = {**settings.ANTHROPIC, "model": "claude-opus-5"}

        assert budget.current_rates().output == Decimal("25.00")


class TestEstimate:
    def test_the_whole_output_allowance_is_priced_in(self):
        estimate = budget.estimate_usd([], max_tokens=8000, rates=budget.current_rates())

        assert estimate >= Decimal("0.04")  # 8000 tokens at $5 per million

    def test_a_prompt_is_never_priced_below_one_token_per_byte_at_the_cache_write_rate(self):
        """No tokenizer yields more tokens than bytes, and a cache write is the dearest way to read input."""
        messages = [{"role": "user", "content": "\U0001f697" * 1000}]  # 1000 characters, 4000 bytes

        estimate = budget.estimate_usd(messages, max_tokens=0, rates=budget.current_rates())

        assert estimate >= Decimal("0.005")  # 4000 tokens at $1.25 per million


class TestReserve:
    def test_the_worst_case_is_recorded_and_counted_as_spent_at_once(self):
        post = BlogPostFactory()

        usage = reserve("0.01", post=post)

        assert (usage.status, usage.reserved_usd, usage.cost_usd) == (
            AiUsage.Status.RESERVED,
            Decimal("0.01"),
            Decimal("0.01"),
        )
        assert usage.blog_post == post
        assert usage.output_usd_per_1m == Decimal("5.00")
        period = BudgetPeriod.objects.get()
        assert (period.spent_usd, period.calls) == (Decimal("0.01"), 1)

    def test_a_call_that_would_cross_the_cap_is_refused_and_leaves_no_trace(self):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("9.995"))

        with pytest.raises(budget.BudgetExceededError) as refused:
            reserve("0.01")

        assert (refused.value.spent_usd, refused.value.cap_usd, refused.value.estimate_usd) == (
            Decimal("9.995"),
            Decimal("10.0"),
            Decimal("0.01"),
        )
        assert AiUsage.objects.count() == 0
        assert spent() == Decimal("9.995")

    def test_a_call_that_lands_exactly_on_the_cap_is_allowed(self):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("9.99"))

        reserve("0.01")

        assert spent() == Decimal("10.00")

    def test_a_zero_cap_disables_the_limit(self, settings):
        settings.AI_BUDGET = {**settings.AI_BUDGET, "monthly_usd": 0}

        reserve("5000")

        assert spent() == Decimal("5000")

    def test_spend_is_grouped_by_calendar_month_in_utc(self, time_machine):
        time_machine.move_to("2026-08-31T23:59:00Z", tick=False)
        reserve("0.01")
        time_machine.move_to("2026-09-01T00:01:00Z", tick=False)
        reserve("0.02")

        assert spent(date(2026, 8, 1)) == Decimal("0.01")
        assert spent(date(2026, 9, 1)) == Decimal("0.02")


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_calls_cannot_both_squeeze_under_the_cap(monkeypatch):
    """Both read $9.985 spent. Without a row lock, both would pass a $10 cap."""
    BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("9.985"))
    rates = budget.current_rates()
    create = AiUsage.objects.create

    def slow_create(**fields):
        # Widens the gap between reading the total and writing it, where a race would land.
        time.sleep(0.3)
        return create(**fields)

    monkeypatch.setattr(AiUsage.objects, "create", slow_create)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt():
        try:
            barrier.wait()
            budget.reserve(blog_post=None, estimate_usd=Decimal("0.01"), model=MODEL, rates=rates)
            outcomes.append("reserved")
        except budget.BudgetExceededError:
            outcomes.append("refused")
        except Exception as error:
            outcomes.append(repr(error))
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(outcomes) == ["refused", "reserved"]
    assert spent() == Decimal("9.995")


class TestSettle:
    def test_the_reservation_is_replaced_by_the_real_cost(self):
        usage = reserve("0.01")

        budget.settle(
            usage, succeeded=True, input_tokens=1234, output_tokens=567, request_id="req_1", stop_reason="end_turn"
        )
        usage.refresh_from_db()

        assert (usage.status, usage.cost_usd, usage.reserved_usd) == (
            AiUsage.Status.SUCCEEDED,
            Decimal("0.004069"),
            Decimal("0.01"),
        )
        assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (1234, 567, 1801)
        assert (usage.request_id, usage.stop_reason) == ("req_1", "end_turn")
        assert usage.settled_at is not None
        assert spent() == Decimal("0.004069")

    def test_the_rates_in_force_at_reservation_price_the_call(self, settings):
        usage = reserve("0.01")
        settings.ANTHROPIC = {
            **settings.ANTHROPIC,
            **dict.fromkeys(
                ("input_usd_per_1m", "output_usd_per_1m", "cache_write_usd_per_1m", "cache_read_usd_per_1m"), "99"
            ),
        }

        budget.settle(usage, succeeded=True, input_tokens=1234, output_tokens=567)

        assert spent() == Decimal("0.004069")

    def test_a_call_that_failed_before_using_tokens_releases_its_reservation(self):
        usage = reserve("0.01")

        budget.settle(usage, succeeded=False)
        usage.refresh_from_db()

        assert (usage.status, usage.cost_usd) == (AiUsage.Status.FAILED, Decimal("0"))
        assert spent() == Decimal("0")

    def test_a_failed_call_that_still_used_tokens_is_charged_for_them(self):
        """A truncated article is discarded, but its tokens were billed."""
        usage = reserve("0.01")

        budget.settle(usage, succeeded=False, input_tokens=1234, output_tokens=567, stop_reason="max_tokens")

        assert spent() == Decimal("0.004069")

    def test_settling_twice_adjusts_the_budget_once(self):
        usage = reserve("0.01")
        budget.settle(usage, succeeded=True, input_tokens=1234, output_tokens=567)

        budget.settle(usage, succeeded=True, input_tokens=1_000_000, output_tokens=1_000_000)

        assert spent() == Decimal("0.004069")

    def test_a_call_that_finishes_after_midnight_is_charged_to_the_month_it_started(self, time_machine):
        time_machine.move_to("2026-08-31T23:59:59Z", tick=False)
        usage = reserve("0.01")
        time_machine.move_to("2026-09-01T00:00:05Z", tick=False)

        budget.settle(usage, succeeded=True, input_tokens=1234, output_tokens=567)

        assert spent(date(2026, 8, 1)) == Decimal("0.004069")
        assert not BudgetPeriod.objects.filter(month=date(2026, 9, 1)).exists()


class TestAbandon:
    def test_a_call_whose_outcome_is_unknown_keeps_its_worst_case_cost(self):
        """A read timeout may follow a completed, billed generation: charging nothing would undercount."""
        usage = reserve("0.01")

        budget.abandon(usage)
        usage.refresh_from_db()

        assert (usage.status, usage.cost_usd) == (AiUsage.Status.ABANDONED, Decimal("0.01"))
        assert usage.settled_at is not None
        assert spent() == Decimal("0.01")

    def test_a_settled_call_cannot_be_abandoned_afterwards(self):
        usage = reserve("0.01")
        budget.settle(usage, succeeded=True, input_tokens=1234, output_tokens=567)

        budget.abandon(usage)
        usage.refresh_from_db()

        assert (usage.status, usage.cost_usd) == (AiUsage.Status.SUCCEEDED, Decimal("0.004069"))


class TestStaleReservations:
    def test_a_reservation_left_by_a_killed_worker_is_abandoned_with_its_cost_kept(self, time_machine):
        time_machine.move_to("2026-09-16T10:00:00Z", tick=False)
        usage = reserve("0.01")
        time_machine.move_to("2026-09-16T10:16:00Z", tick=False)

        assert budget.reconcile_stale_reservations() == 1

        usage.refresh_from_db()
        assert (usage.status, usage.cost_usd) == (AiUsage.Status.ABANDONED, Decimal("0.01"))
        assert spent() == Decimal("0.01")
        event = ErrorEvent.objects.get()
        assert (event.context, event.severity) == (ErrorEvent.Context.AI_BUDGET, ErrorEvent.Severity.WARNING)

    def test_a_slow_call_presumed_abandoned_is_still_charged_its_real_cost(self, time_machine):
        time_machine.move_to("2026-09-16T10:00:00Z", tick=False)
        usage = reserve("0.01")
        time_machine.move_to("2026-09-16T10:16:00Z", tick=False)
        budget.reconcile_stale_reservations()

        budget.settle(usage, succeeded=True, input_tokens=1234, output_tokens=567)

        assert spent() == Decimal("0.004069")

    def test_a_reservation_still_in_flight_is_left_alone(self, time_machine):
        time_machine.move_to("2026-09-16T10:00:00Z", tick=False)
        usage = reserve("0.01")
        time_machine.move_to("2026-09-16T10:05:00Z", tick=False)

        assert budget.reconcile_stale_reservations() == 0

        usage.refresh_from_db()
        assert usage.status == AiUsage.Status.RESERVED
        assert not ErrorEvent.objects.exists()


class TestMonthToDate:
    def test_an_untouched_month_reads_as_zero_without_creating_a_row(self):
        summary = budget.month_to_date()

        assert (summary["spent_usd"], summary["calls"], summary["remaining_usd"]) == (
            Decimal("0"),
            0,
            Decimal("10.0"),
        )
        assert not BudgetPeriod.objects.exists()

    def test_spend_is_reported_against_the_cap(self):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("8.5"), calls=3)

        summary = budget.month_to_date()

        assert (summary["cap_usd"], summary["remaining_usd"], summary["percent_used"], summary["calls"]) == (
            Decimal("10.0"),
            Decimal("1.5"),
            85,
            3,
        )

    def test_spend_past_a_lowered_cap_leaves_nothing_remaining_rather_than_a_negative(self):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("12"))

        summary = budget.month_to_date()

        assert (summary["remaining_usd"], summary["percent_used"]) == (Decimal("0"), 120)

    def test_without_a_cap_there_is_no_remaining_or_percentage(self, settings):
        settings.AI_BUDGET = {**settings.AI_BUDGET, "monthly_usd": 0}

        summary = budget.month_to_date()

        assert (summary["cap_usd"], summary["remaining_usd"], summary["percent_used"]) == (None, None, None)


class TestRecompute:
    def test_the_running_total_always_equals_the_usage_rows(self):
        budget.settle(reserve("0.01"), succeeded=True, input_tokens=1234, output_tokens=567)
        budget.settle(reserve("0.02"), succeeded=False)
        reserve("0.03")

        assert spent() == sum(AiUsage.objects.values_list("cost_usd", flat=True))

    def test_a_drifted_total_is_rebuilt_from_the_usage_rows_of_that_month_only(self, time_machine):
        time_machine.move_to("2026-08-15T12:00:00Z", tick=False)
        reserve("0.50")
        time_machine.move_to("2026-09-15T12:00:00Z", tick=False)
        reserve("0.01")
        reserve("0.02")
        BudgetPeriod.objects.filter(month=date(2026, 9, 1)).update(spent_usd=Decimal("7"), calls=40)

        period = budget.recompute_period(date(2026, 9, 1))

        assert (period.spent_usd, period.calls) == (Decimal("0.03"), 2)
        assert spent(date(2026, 8, 1)) == Decimal("0.50")

    def test_december_is_bounded_by_new_year_not_by_a_thirteenth_month(self, time_machine):
        time_machine.move_to("2026-12-31T23:59:59Z", tick=False)
        reserve("0.04")
        time_machine.move_to("2027-01-01T00:00:00Z", tick=False)
        reserve("0.05")

        assert budget.recompute_period(date(2026, 12, 1)).spent_usd == Decimal("0.04")
        assert budget.recompute_period(date(2027, 1, 1)).spent_usd == Decimal("0.05")
