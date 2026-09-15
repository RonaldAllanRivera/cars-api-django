from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts import abilities
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch
from tests.api.helpers import error_fields, ids
from tests.factories import ErrorEventFactory

pytestmark = pytest.mark.django_db


def test_both_endpoints_require_the_errors_read_ability(client, acting_as):
    assert client.get("/api/v1/health/summary").status_code == 401
    assert client.get("/api/v1/errors").status_code == 401

    acting_as([abilities.SEARCH_READ])
    assert client.get("/api/v1/health/summary").status_code == 403
    assert client.get("/api/v1/errors").status_code == 403


def test_the_summary_counts_runs_errors_and_images_in_their_windows(client, acting_as, make_search, make_image):
    user = acting_as([abilities.ERRORS_READ])
    make_search(user, status=CarSearch.Status.COMPLETED)
    make_search(user, status=CarSearch.Status.COMPLETED)
    make_image(make_search(user, status=CarSearch.Status.FAILED))
    now = timezone.now()
    ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN, occurred_at=now)
    ErrorEventFactory(context=ErrorEvent.Context.WIKIMEDIA_BLOCK, occurred_at=now - timedelta(days=3))
    ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, occurred_at=now - timedelta(days=10))

    data = client.get("/api/v1/health/summary").json()["data"]

    assert data["searches_by_status"] == {"pending": 0, "running": 0, "completed": 2, "failed": 1}
    assert data["errors_last_24h"] == 1
    assert data["errors_by_context_last_7d"] == {
        "csv_upload": 0,
        "csv_row": 0,
        "search_run": 1,
        "image_download": 0,
        "wikimedia_block": 1,
    }
    assert data["images_last_7d"] == 1
    assert isinstance(data["latest_error_at"], str)
    assert data["latest_error_at"].endswith("+00:00")


def test_an_empty_database_still_returns_every_key(client, acting_as):
    acting_as([abilities.ERRORS_READ])

    data = client.get("/api/v1/health/summary").json()["data"]

    assert data["searches_by_status"]["completed"] == 0
    assert data["errors_by_context_last_7d"]["csv_upload"] == 0
    assert data["latest_error_at"] is None


def test_errors_are_listed_newest_first_and_filterable(client, acting_as):
    acting_as([abilities.ERRORS_READ])
    old = ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN, occurred_at=timezone.now() - timedelta(hours=1))
    new = ErrorEventFactory(context=ErrorEvent.Context.IMAGE_DOWNLOAD, severity=ErrorEvent.Severity.WARNING)

    response = client.get("/api/v1/errors")
    assert ids(response) == [new.id, old.id]
    body = response.json()
    assert list(body["data"][0]) == [
        "id",
        "context",
        "severity",
        "message",
        "exception_class",
        "exception_message",
        "trace_excerpt",
        "details",
        "car_search_id",
        "csv_import_id",
        "car_image_id",
        "occurred_at",
    ]
    assert {"next_cursor", "prev_cursor", "per_page"} <= set(body["meta"])

    assert ids(client.get("/api/v1/errors?context=search_run")) == [old.id]
    assert ids(client.get("/api/v1/errors?severity=warning")) == [new.id]
    assert error_fields(client.get("/api/v1/errors?context=meteor_strike")) == {"context"}


def test_errors_logged_in_the_same_instant_page_without_skipping(client, acting_as):
    acting_as([abilities.ERRORS_READ])
    instant = timezone.now()
    events = [ErrorEventFactory(occurred_at=instant) for _ in range(3)]
    earlier = ErrorEventFactory(occurred_at=instant - timedelta(minutes=1))

    seen: list[int] = []
    url = "/api/v1/errors?per_page=2"
    while url:
        body = client.get(url).json()
        seen += [row["id"] for row in body["data"]]
        cursor = body["meta"]["next_cursor"]
        url = f"/api/v1/errors?per_page=2&cursor={cursor}" if cursor else None

    assert seen == [*(event.id for event in reversed(events)), earlier.id]
