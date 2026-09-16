from datetime import timedelta

import pytest
from django.utils import timezone

from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.observability.services.health import PIPELINE_CONTEXTS, pipeline_health_summary
from apps.searches.models import CarSearch
from tests.factories import CarImageFactory, CarSearchFactory, ErrorEventFactory

pytestmark = pytest.mark.django_db


def test_the_summary_counts_runs_errors_and_images_in_their_windows():
    now = timezone.now()
    CarSearchFactory.create_batch(2, status=CarSearch.Status.COMPLETED)
    failed = CarSearchFactory(status=CarSearch.Status.FAILED)
    CarImageFactory(car_search=failed)
    old_image = CarImageFactory(car_search=failed)
    CarImage.objects.filter(pk=old_image.pk).update(created_at=now - timedelta(days=8))
    latest = ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN, occurred_at=now - timedelta(minutes=5))
    ErrorEventFactory(context=ErrorEvent.Context.WIKIMEDIA_BLOCK, occurred_at=now - timedelta(days=3))
    ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, occurred_at=now - timedelta(days=10))

    summary = pipeline_health_summary()

    assert summary == {
        "searches_by_status": {"pending": 0, "running": 0, "completed": 2, "failed": 1},
        "errors_last_24h": 1,
        "errors_by_context_last_7d": {
            "csv_upload": 0,
            "csv_row": 0,
            "search_run": 1,
            "image_download": 0,
            "wikimedia_block": 1,
        },
        "images_last_7d": 1,
        "latest_error_at": latest.occurred_at,
    }
    assert list(summary["errors_by_context_last_7d"]) == list(PIPELINE_CONTEXTS)


def test_latest_error_is_the_newest_by_occurrence_not_by_insertion():
    newest = ErrorEventFactory(occurred_at=timezone.now() - timedelta(hours=1))
    ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=40))

    assert pipeline_health_summary()["latest_error_at"] == newest.occurred_at


def test_an_empty_database_still_returns_every_key():
    assert pipeline_health_summary() == {
        "searches_by_status": {"pending": 0, "running": 0, "completed": 0, "failed": 0},
        "errors_last_24h": 0,
        "errors_by_context_last_7d": {
            "csv_upload": 0,
            "csv_row": 0,
            "search_run": 0,
            "image_download": 0,
            "wikimedia_block": 0,
        },
        "images_last_7d": 0,
        "latest_error_at": None,
    }


def test_a_publishing_context_does_not_change_the_health_wire_shape():
    """
    Deployed clients validate errors_by_context_last_7d against a closed enum, so
    a new ErrorEvent.Context must not add a key until they ship an update.
    """
    ErrorEventFactory(context=ErrorEvent.Context.AI_GENERATION)

    counts = pipeline_health_summary()["errors_by_context_last_7d"]

    assert "ai_generation" not in counts
    assert list(counts) == list(PIPELINE_CONTEXTS)
