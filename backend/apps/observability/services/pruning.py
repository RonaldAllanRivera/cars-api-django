"""
Port of the error-events:prune retention rule.

Deliberately not scheduled: pruning is operator-triggered. Every trigger
(the `prune_error_events` command included) calls prune(), so the retention
rule has exactly one implementation.
"""

from datetime import timedelta

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.observability.models import ErrorEvent


def retention_days() -> int:
    return int(settings.CARS_IMAGES["error_log_retention_days"])


def prunable_count() -> int:
    return _expired().count()


def prune() -> int:
    """Delete events older than the retention window; returns how many went."""
    deleted, _ = _expired().delete()
    return deleted


def _expired() -> QuerySet[ErrorEvent]:
    return ErrorEvent.objects.filter(occurred_at__lt=timezone.now() - timedelta(days=retention_days()))
