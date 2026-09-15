from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.observability.models import ErrorEvent
from apps.observability.services import pruning
from tests.factories import ErrorEventFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def thirty_day_retention(settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "error_log_retention_days": 30}


def run_prune() -> str:
    out = StringIO()
    call_command("prune_error_events", stdout=out)
    return out.getvalue()


def test_deletes_events_older_than_the_retention_window():
    stale = ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=31))
    fresh = ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=29))

    output = run_prune()

    assert output.strip() == "Deleted 1 error event(s) older than 30 day(s)."
    assert not ErrorEvent.objects.filter(pk=stale.pk).exists()
    assert ErrorEvent.objects.filter(pk=fresh.pk).exists()


def test_keeps_an_event_exactly_on_the_boundary():
    boundary = ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=30) + timedelta(minutes=1))

    run_prune()

    assert ErrorEvent.objects.filter(pk=boundary.pk).exists()


def test_reports_when_there_is_nothing_to_prune():
    assert run_prune().strip() == "Deleted 0 error event(s) older than 30 day(s)."


def test_the_service_counts_before_it_deletes(settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "error_log_retention_days": 7}
    ErrorEventFactory.create_batch(2, occurred_at=timezone.now() - timedelta(days=8))
    ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=6))

    assert pruning.retention_days() == 7
    assert pruning.prunable_count() == 2
    assert pruning.prune() == 2
    assert pruning.prunable_count() == 0
    assert ErrorEvent.objects.count() == 1
