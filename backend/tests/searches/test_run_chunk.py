from types import SimpleNamespace

import httpx
import pytest

from apps.searches.models import CarSearch, WikimediaBlockEvent
from apps.searches.services import run_chunk as run_chunk_module
from apps.searches.services.run_chunk import ChunkBlocked, ChunkOutcome, run_chunk
from tests.factories import CarSearchFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def empty_commons(commons):
    """Commons returning nothing: every search completes having found no images."""
    return commons.route().mock(return_value=httpx.Response(200, json={"query": {"pages": []}}))


@pytest.fixture
def make_search(user, csv_import):
    def factory(**fields) -> CarSearch:
        return CarSearchFactory(
            requested_by=user, **{"csv_import": csv_import, "status": CarSearch.Status.PENDING, **fields}
        )

    return factory


def _cars_images_settings(settings, **overrides) -> None:
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, **overrides}


def test_it_runs_the_imports_pending_searches(empty_commons, csv_import, make_search):
    a = make_search()
    b = make_search()

    result = run_chunk(csv_import.pk)

    assert [outcome.id for outcome in result.outcomes] == [a.pk, b.pk]
    assert result.remaining == 0
    assert result.blocked is None
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.status, b.status) == (CarSearch.Status.COMPLETED, CarSearch.Status.COMPLETED)


def test_it_stops_at_the_chunk_size_and_reports_what_is_left(empty_commons, settings, csv_import, make_search):
    _cars_images_settings(settings, bulk_run_max_queries_per_chunk=1)
    first = make_search()
    make_search()

    result = run_chunk(csv_import.pk)

    assert [outcome.id for outcome in result.outcomes] == [first.pk], "Searches run in CSV (id) order."
    assert result.remaining == 1


def test_it_names_the_car_in_each_outcome(empty_commons, csv_import, make_search):
    search = make_search(make="Honda", model="Civic", from_year=1998, to_year=1998)

    [outcome] = run_chunk(csv_import.pk).outcomes

    assert outcome == ChunkOutcome(id=search.pk, make="Honda", model="Civic", from_year=1998, outcome="completed")


def test_it_includes_failed_searches_as_runnable(empty_commons, csv_import, make_search):
    failed = make_search(status=CarSearch.Status.FAILED)

    run_chunk(csv_import.pk)

    failed.refresh_from_db()
    assert failed.status == CarSearch.Status.COMPLETED


@pytest.mark.parametrize("status", [CarSearch.Status.COMPLETED, CarSearch.Status.RUNNING])
def test_it_leaves_searches_that_are_not_runnable_alone(empty_commons, csv_import, make_search, status):
    other = make_search(status=status)

    result = run_chunk(csv_import.pk)

    assert result.outcomes == []
    assert result.remaining == 0
    other.refresh_from_db()
    assert other.status == status


def test_a_single_failure_does_not_abandon_the_rest(commons, csv_import, make_search):
    bad = make_search(make="Bad")
    good = make_search(make="Good")
    commons.route().mock(
        side_effect=lambda request: (
            httpx.Response(500, text="kaboom")
            if "Bad" in str(request.url)
            else httpx.Response(200, json={"query": {"pages": []}})
        )
    )

    result = run_chunk(csv_import.pk)

    assert [(outcome.id, outcome.outcome) for outcome in result.outcomes] == [
        (bad.pk, "failed"),
        (good.pk, "completed"),
    ]
    assert result.blocked is None
    assert result.remaining == 1, "The failed search is still work to do."
    bad.refresh_from_db()
    good.refresh_from_db()
    assert (bad.status, good.status) == (CarSearch.Status.FAILED, CarSearch.Status.COMPLETED)


def test_a_wikimedia_block_halts_the_chunk_and_reports_the_window(commons, csv_import, make_search):
    route = commons.route().mock(
        return_value=httpx.Response(429, text="Too Many Requests", headers={"Retry-After": "600"})
    )
    make_search()
    untouched = make_search()

    result = run_chunk(csv_import.pk)

    assert result.blocked == ChunkBlocked(status=429, retry_after_seconds=600)
    assert result.outcomes == []
    assert route.call_count == 1, "The second search was never attempted."
    assert WikimediaBlockEvent.objects.count() == 1
    assert result.remaining == 2
    untouched.refresh_from_db()
    assert untouched.status == CarSearch.Status.PENDING


def test_an_empty_queue_is_not_an_error(csv_import):
    result = run_chunk(csv_import.pk)

    assert result.outcomes == []
    assert result.remaining == 0
    assert result.blocked is None


def test_it_ignores_searches_from_other_imports(empty_commons, user, csv_import, make_search):
    not_mine = make_search(csv_import=CsvImportFactory(imported_by=user))

    run_chunk(csv_import.pk)

    not_mine.refresh_from_db()
    assert not_mine.status == CarSearch.Status.PENDING


def test_the_chunk_is_time_boxed_but_always_runs_at_least_one_search(
    empty_commons, settings, monkeypatch, csv_import, make_search
):
    _cars_images_settings(settings, bulk_run_auto_chunk_seconds=10)
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(run_chunk_module, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=lambda _: None))
    real_run = run_chunk_module.run_search_query

    def slow_run(search):
        clock.now += 6
        return real_run(search)

    monkeypatch.setattr(run_chunk_module, "run_search_query", slow_run)
    for _ in range(3):
        make_search()

    result = run_chunk(csv_import.pk)

    assert len(result.outcomes) == 2, "The third search starts after the 10 s box has elapsed."
    assert result.remaining == 1
    assert result.ran_seconds == 12.0


def test_it_paces_between_searches_but_not_after_the_last(
    empty_commons, settings, monkeypatch, csv_import, make_search
):
    _cars_images_settings(settings, bulk_run_sleep_seconds_between_queries=1.5)
    sleeps: list[float] = []
    monkeypatch.setattr(run_chunk_module, "time", SimpleNamespace(monotonic=lambda: 0.0, sleep=sleeps.append))
    for _ in range(3):
        make_search()

    run_chunk(csv_import.pk)

    assert sleeps == [1.5, 1.5]


def test_the_result_serialises_to_plain_data(commons, csv_import, make_search):
    commons.route().mock(return_value=httpx.Response(503, text="Service Unavailable"))
    make_search()

    data = run_chunk(csv_import.pk).as_dict()

    assert data["outcomes"] == []
    assert data["blocked"] == {"status": 503, "retry_after_seconds": None}
    assert data["remaining"] == 1
    assert isinstance(data["ran_seconds"], float)
