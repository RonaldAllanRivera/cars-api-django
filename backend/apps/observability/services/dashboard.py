"""
Numbers and chart geometry for the admin landing page.

Ports the four Filament dashboard widgets. Every figure is scoped to a window:
"is the pipeline broken now" is a different question from "has it ever broken",
and an all-time error count would read as alarming forever.

Chart shapes are computed here rather than in the template so they can be
tested, and drawn as inline SVG so the admin needs no charting library.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch

ERROR_WINDOW_DAYS = 14
THROUGHPUT_WINDOW_DAYS = 30
SPARKLINE_DAYS = 7
LATEST_FAILURES = 10

# Distinct hues per context, matching the Laravel dashboard.
CONTEXT_CHART_COLORS = {
    ErrorEvent.Context.WIKIMEDIA_BLOCK: "#dc2626",
    ErrorEvent.Context.CSV_ROW: "#d97706",
    ErrorEvent.Context.CSV_UPLOAD: "#7c3aed",
    ErrorEvent.Context.SEARCH_RUN: "#2563eb",
    ErrorEvent.Context.IMAGE_DOWNLOAD: "#0891b2",
}
STATUS_CHART_COLORS = {CarSearch.Status.COMPLETED: "#16a34a", CarSearch.Status.FAILED: "#dc2626"}

CHART_WIDTH = 720
CHART_HEIGHT = 160
# Keeps the stroke off the top and bottom edges, where it would be clipped in half.
CHART_INSET = 6


@dataclass
class Stat:
    label: str
    value: int | str
    description: str
    tone: str = "neutral"  # neutral | good | warn | bad
    url: str | None = None
    sparkline: str | None = None


@dataclass
class BarSegment:
    label: str
    color: str
    count: int
    height_percent: float


@dataclass
class BarDay:
    label: str
    total: int
    height_percent: float
    segments: list[BarSegment] = field(default_factory=list)

    def __str__(self) -> str:
        return self.label


def dashboard_metrics() -> dict:
    today = timezone.localdate()
    return {
        "stats": _stats(today),
        "errors_by_context": _errors_by_context(today),
        "throughput": _throughput(today),
        "latest_failures": _latest_failures(),
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def _stats(today: date) -> list[Stat]:
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    errors_24h = ErrorEvent.objects.filter(occurred_at__gte=now - timedelta(days=1)).count()
    failed_searches = CarSearch.objects.filter(status=CarSearch.Status.FAILED, created_at__gte=week_ago).count()
    images = CarImage.objects.filter(created_at__gte=week_ago).count()

    daily_errors = _counts_by_day(ErrorEvent.objects.all(), "occurred_at", _days(today, SPARKLINE_DAYS))

    return [
        Stat(
            label="Errors (24h)",
            value=errors_24h,
            description="Pipeline is quiet" if errors_24h == 0 else "Open the error log",
            tone="good" if errors_24h == 0 else "bad",
            url=reverse("admin:observability_errorevent_changelist"),
            sparkline=_polyline(daily_errors),
        ),
        Stat(
            label="Failed searches (7d)",
            value=failed_searches,
            description="Queries that ended in failure",
            tone="good" if failed_searches == 0 else "warn",
            url=reverse("admin:searches_carsearch_changelist") + "?status__exact=failed",
        ),
        Stat(
            label="Images collected (7d)",
            value=images,
            description="New rows in the image library",
            url=reverse("admin:images_carimage_changelist"),
        ),
        _latest_import_stat(),
    ]


def _latest_import_stat() -> Stat:
    """
    csv_imports records what an import contained, never whether it worked.
    The only honest verdict available is the errors linked back to it.
    """
    latest = CsvImport.objects.order_by("-id").first()
    if latest is None:
        return Stat(label="Latest import", value="None yet", description="No CSV uploaded yet")

    errors = ErrorEvent.objects.filter(csv_import=latest).count()
    return Stat(
        label="Latest import",
        value=latest.original_filename,
        description="No errors" if errors == 0 else f"{errors} error{'s' if errors != 1 else ''}",
        tone="good" if errors == 0 else "warn",
        url=reverse("admin:imports_csvimport_change", args=[latest.pk]),
    )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def _errors_by_context(today: date) -> dict:
    """
    Stacked, because the question is "how bad was that day" first and "which
    kind" second. Only contexts that actually failed get a legend entry: five
    permanently empty series would bury the one that matters.
    """
    days = _days(today, ERROR_WINDOW_DAYS)
    rows = (
        ErrorEvent.objects.filter(occurred_at__date__gte=days[0])
        .annotate(day=TruncDate("occurred_at"))
        .values("day", "context")
        .annotate(total=Count("pk"))
    )
    per_day: dict[date, dict[str, int]] = {day: {} for day in days}
    for row in rows:
        if row["day"] in per_day:
            per_day[row["day"]][row["context"]] = row["total"]

    contexts = [context for context in ErrorEvent.Context if any(context in counts for counts in per_day.values())]
    labels = dict(ErrorEvent.Context.choices)
    peak = max((sum(counts.values()) for counts in per_day.values()), default=0)

    bars = []
    for day in days:
        counts = per_day[day]
        total = sum(counts.values())
        bars.append(
            BarDay(
                label=day.strftime("%-d %b"),
                total=total,
                height_percent=_percent(total, peak),
                segments=[
                    BarSegment(
                        label=labels[context],
                        color=CONTEXT_CHART_COLORS[context],
                        count=counts[context],
                        height_percent=_percent(counts[context], total),
                    )
                    for context in contexts
                    if counts.get(context)
                ],
            )
        )

    return {
        "days": bars,
        "peak": peak,
        "legend": [{"label": labels[context], "color": CONTEXT_CHART_COLORS[context]} for context in contexts],
        "window_days": ERROR_WINDOW_DAYS,
    }


def _throughput(today: date) -> dict:
    """Both series are always drawn, so the legend keeps its shape in a quiet week."""
    days = _days(today, THROUGHPUT_WINDOW_DAYS)
    rows = (
        CarSearch.objects.filter(status__in=STATUS_CHART_COLORS, created_at__date__gte=days[0])
        .annotate(day=TruncDate("created_at"))
        .values("day", "status")
        .annotate(total=Count("pk"))
    )
    per_status: dict[str, dict[date, int]] = {status: {} for status in STATUS_CHART_COLORS}
    for row in rows:
        per_status[row["status"]][row["day"]] = row["total"]

    counts = {status: [per_status[status].get(day, 0) for day in days] for status in STATUS_CHART_COLORS}
    peak = max((value for series in counts.values() for value in series), default=0)

    return {
        "series": [
            {
                "label": CarSearch.Status(status).label,
                "color": color,
                "points": _polyline(counts[status], peak=peak),
                "total": sum(counts[status]),
            }
            for status, color in STATUS_CHART_COLORS.items()
        ],
        "peak": peak,
        "labels": [days[0].strftime("%-d %b"), days[len(days) // 2].strftime("%-d %b"), days[-1].strftime("%-d %b")],
        "window_days": THROUGHPUT_WINDOW_DAYS,
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
    }


def _latest_failures() -> list[dict]:
    """A shortcut into the error log, not a second copy of it: ten rows, no filters."""
    return [
        {
            "occurred_at": event.occurred_at,
            "label": event.get_context_display(),
            "color": CONTEXT_CHART_COLORS[event.context],
            "message": event.message or event.exception_message or "",
            "url": reverse("admin:observability_errorevent_change", args=[event.pk]),
        }
        for event in ErrorEvent.objects.order_by("-occurred_at", "-id")[:LATEST_FAILURES]
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _days(today: date, count: int) -> list[date]:
    return [today - timedelta(days=offset) for offset in range(count - 1, -1, -1)]


def _counts_by_day(queryset, field_name: str, days: list[date]) -> list[int]:
    rows = (
        queryset.filter(**{f"{field_name}__date__gte": days[0]})
        .annotate(day=TruncDate(field_name))
        .values("day")
        .annotate(total=Count("pk"))
    )
    counts = {row["day"]: row["total"] for row in rows}
    return [counts.get(day, 0) for day in days]


def _percent(value: int, total: int) -> float:
    return round(value / total * 100, 2) if total else 0.0


def _polyline(values: list[int], *, peak: int | None = None, width: int = CHART_WIDTH, height: int = CHART_HEIGHT):
    """SVG polyline points, left to right, with y inverted (0 is the top)."""
    if not values:
        return ""
    ceiling = peak if peak is not None else max(values)
    step = width / (len(values) - 1) if len(values) > 1 else 0
    plot = height - 2 * CHART_INSET
    return " ".join(
        f"{round(index * step, 1)},{round(height - CHART_INSET - (value / ceiling * plot if ceiling else 0), 1)}"
        for index, value in enumerate(values)
    )
