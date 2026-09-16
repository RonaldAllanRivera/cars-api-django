"""
Structured pipeline error log. `record()` never raises: a failure to log must
not turn a recoverable pipeline error into a crash.
"""

import logging
import traceback
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.observability.models import ErrorEvent

logger = logging.getLogger(__name__)

MESSAGE_BYTES = 500
EXCEPTION_MESSAGE_BYTES = 2000
DETAIL_STRING_BYTES = 1000
TRACE_FRAMES = 15


def clamp(value: str | None, max_bytes: int) -> str | None:
    """
    Truncate to max_bytes of UTF-8 without splitting a character; scrub invalid
    bytes, and NULs, which PostgreSQL rejects in both text and jsonb.
    """
    if value is None:
        return None
    encoded = value.replace("\x00", "").encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return encoded.decode("utf-8", errors="replace")
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _clamp_details(details: Any) -> Any:
    if isinstance(details, dict):
        return {str(key): _clamp_details(value) for key, value in details.items()}
    if isinstance(details, (list, tuple)):
        return [_clamp_details(value) for value in details]
    if isinstance(details, str):
        return clamp(details, DETAIL_STRING_BYTES)
    return details


def _trace_excerpt(error: BaseException) -> str | None:
    frames = traceback.extract_tb(error.__traceback__)[-TRACE_FRAMES:]
    if not frames:
        return None
    return "".join(traceback.format_list(frames)).rstrip()


def record(
    context: str,
    error: BaseException | str,
    *,
    car_search=None,
    csv_import=None,
    car_image=None,
    blog_post=None,
    details: dict | None = None,
    severity: str = ErrorEvent.Severity.ERROR,
    message: str | None = None,
) -> ErrorEvent | None:
    try:
        import_id = getattr(csv_import, "pk", csv_import)
        cap = settings.CARS_IMAGES["error_log_max_events_per_import"]
        if import_id is not None and cap > 0:
            existing = ErrorEvent.objects.filter(csv_import_id=import_id).count()
            if existing > cap:
                return None
            if existing == cap:
                return ErrorEvent.objects.create(
                    context=context,
                    severity=ErrorEvent.Severity.WARNING,
                    message=f"Further errors for this import were suppressed after {cap} events.",
                    csv_import_id=import_id,
                    occurred_at=timezone.now(),
                )

        fields: dict[str, Any] = {
            "context": context,
            "severity": severity,
            "details": _clamp_details(details) if details else None,
            "car_search_id": getattr(car_search, "pk", car_search),
            "csv_import_id": import_id,
            "car_image_id": getattr(car_image, "pk", car_image),
            "blog_post_id": getattr(blog_post, "pk", blog_post),
            "occurred_at": timezone.now(),
        }
        if isinstance(error, BaseException):
            fields.update(
                message=clamp(message or str(error) or type(error).__name__, MESSAGE_BYTES),
                exception_class=type(error).__name__,
                exception_message=clamp(str(error), EXCEPTION_MESSAGE_BYTES),
                trace_excerpt=_trace_excerpt(error),
            )
        else:
            fields["message"] = clamp(message or error, MESSAGE_BYTES)

        return ErrorEvent.objects.create(**fields)
    except Exception:  # never let logging break the pipeline
        logger.exception("Failed to record %s error event", context)
        return None
