"""Runs one search: marks failures, logs them, re-raises."""

from django.utils import timezone

from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.searches.models import CarSearch, WikimediaBlockEvent
from apps.searches.services.search_service import mark_failed, run_search
from apps.searches.services.wikimedia import WikimediaBlockedError


def run_search_query(search: CarSearch) -> CarSearch:
    """Run one search synchronously. Every failure marks it failed and is logged before re-raising,
    so a bulk loop can swallow the exception; a block also records a WikimediaBlockEvent."""
    try:
        return run_search(search)
    except WikimediaBlockedError as error:
        mark_failed(search)
        WikimediaBlockEvent.objects.create(
            car_search=search,
            csv_import_id=search.csv_import_id,
            status_code=error.status,
            retry_after_seconds=error.retry_after_seconds,
            response_excerpt=error.response_excerpt,
            occurred_at=timezone.now(),
        )
        error_logger.record(
            ErrorEvent.Context.WIKIMEDIA_BLOCK,
            error,
            car_search=search,
            csv_import=search.csv_import_id,
            details={
                "http_status": error.status,
                "retry_after_seconds": error.retry_after_seconds,
                "response_excerpt": error.response_excerpt,
            },
            message=f"{_describe(search)} — blocked by Wikimedia (HTTP {error.status})",
        )
        raise
    except Exception as error:
        mark_failed(search)
        error_logger.record(
            ErrorEvent.Context.SEARCH_RUN,
            error,
            car_search=search,
            csv_import=search.csv_import_id,
            message=f"{_describe(search)} — search failed",
        )
        raise


def _describe(search: CarSearch) -> str:
    """How a query reads in the log: the car, not an id."""
    years = str(search.from_year) if search.from_year == search.to_year else f"{search.from_year}-{search.to_year}"
    return f"{search.make} {search.model or ''} {years}"
