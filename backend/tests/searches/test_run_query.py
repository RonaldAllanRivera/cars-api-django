import httpx
import pytest

from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch, WikimediaBlockEvent
from apps.searches.services.run_query import run_search_query
from apps.searches.services.wikimedia import WikimediaBlockedError
from tests.factories import CarSearchFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def imported_search(user, csv_import):
    return CarSearchFactory(
        requested_by=user,
        csv_import=csv_import,
        make="Toyota",
        model="RAV4",
        from_year=1997,
        to_year=1997,
        images_per_year=5,
        status=CarSearch.Status.PENDING,
    )


def test_marks_the_search_completed_on_success(commons, imported_search):
    commons.route().mock(return_value=httpx.Response(200, json={"query": {"search": []}}))

    result = run_search_query(imported_search)

    imported_search.refresh_from_db()
    assert result.pk == imported_search.pk
    assert imported_search.status == CarSearch.Status.COMPLETED
    assert WikimediaBlockEvent.objects.count() == 0
    assert ErrorEvent.objects.count() == 0


def test_a_429_marks_the_search_failed_records_the_block_and_re_raises(commons, imported_search):
    commons.route().mock(return_value=httpx.Response(429, text="Rate limit exceeded", headers={"Retry-After": "120"}))

    with pytest.raises(WikimediaBlockedError):
        run_search_query(imported_search)

    imported_search.refresh_from_db()
    assert imported_search.status == CarSearch.Status.FAILED

    event = WikimediaBlockEvent.objects.get()
    assert event.status_code == 429
    assert event.retry_after_seconds == 120
    assert event.car_search_id == imported_search.pk
    assert event.csv_import_id == imported_search.csv_import_id
    assert "Rate limit" in event.response_excerpt


def test_a_block_is_written_to_the_error_log_naming_the_car(commons, imported_search):
    commons.route().mock(return_value=httpx.Response(429, text="Rate limit exceeded", headers={"Retry-After": "120"}))

    with pytest.raises(WikimediaBlockedError):
        run_search_query(imported_search)

    error = ErrorEvent.objects.get()
    assert error.context == ErrorEvent.Context.WIKIMEDIA_BLOCK
    assert error.message == "Toyota RAV4 1997 — blocked by Wikimedia (HTTP 429)"
    assert error.exception_class == "WikimediaBlockedError"
    assert error.car_search_id == imported_search.pk
    assert error.csv_import_id == imported_search.csv_import_id
    assert error.details == {
        "http_status": 429,
        "retry_after_seconds": 120,
        "response_excerpt": "Rate limit exceeded",
    }


def test_a_generic_failure_marks_the_search_failed_without_a_block_event(commons, imported_search):
    commons.route().mock(return_value=httpx.Response(500, text="Internal server error"))

    with pytest.raises(httpx.HTTPStatusError):
        run_search_query(imported_search)

    imported_search.refresh_from_db()
    assert imported_search.status == CarSearch.Status.FAILED
    assert WikimediaBlockEvent.objects.count() == 0, "A generic 500 must not create a block event."

    error = ErrorEvent.objects.get()
    assert error.context == ErrorEvent.Context.SEARCH_RUN
    assert error.message == "Toyota RAV4 1997 — search failed"
    assert error.car_search_id == imported_search.pk
    assert error.csv_import_id == imported_search.csv_import_id


def test_a_year_range_is_named_as_a_range_in_the_log(commons, user):
    search = CarSearchFactory(requested_by=user, make="Honda", model="Civic", from_year=1998, to_year=2001)
    commons.route().mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        run_search_query(search)

    error = ErrorEvent.objects.get()
    assert error.message == "Honda Civic 1998-2001 — search failed"
    assert error.csv_import_id is None
