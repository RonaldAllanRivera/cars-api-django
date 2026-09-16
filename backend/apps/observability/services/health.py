"""
The numbers behind the health screen.

Every key is always present, zero-filled, so clients never special-case a
missing one. "Is the pipeline broken now" (24h) and "this week" (7d) are
deliberately separate windows.
"""

from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone

from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch

# The context keys this endpoint promises. Deliberately a frozen list rather than
# ErrorEvent.Context.values: deployed clients validate the dict against a closed
# enum, so adding a context server-side would break their parsing of this response.
# A new context joins this tuple only once the clients that read it can accept it.
PIPELINE_CONTEXTS = (
    ErrorEvent.Context.CSV_UPLOAD,
    ErrorEvent.Context.CSV_ROW,
    ErrorEvent.Context.SEARCH_RUN,
    ErrorEvent.Context.IMAGE_DOWNLOAD,
    ErrorEvent.Context.WIKIMEDIA_BLOCK,
)


def pipeline_health_summary() -> dict:
    """latest_error_at is a datetime or None; formatting it is the API layer's job."""
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    return {
        "searches_by_status": _zero_filled(CarSearch.objects.all(), "status", CarSearch.Status.values),
        "errors_last_24h": ErrorEvent.objects.filter(occurred_at__gte=now - timedelta(days=1)).count(),
        "errors_by_context_last_7d": _zero_filled(
            ErrorEvent.objects.filter(occurred_at__gte=week_ago), "context", list(PIPELINE_CONTEXTS)
        ),
        "images_last_7d": CarImage.objects.filter(created_at__gte=week_ago).count(),
        "latest_error_at": ErrorEvent.objects.aggregate(latest=Max("occurred_at"))["latest"],
    }


def _zero_filled(queryset, field: str, keys: list[str]) -> dict[str, int]:
    counts = dict(queryset.order_by().values_list(field).annotate(total=Count("pk")))
    return {key: counts.get(key, 0) for key in keys}
