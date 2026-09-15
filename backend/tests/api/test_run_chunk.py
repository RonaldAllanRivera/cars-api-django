from unittest import mock

import httpx
import pytest

from apps.accounts import abilities
from apps.searches.models import CarSearch
from apps.searches.services.run_chunk import ChunkResult
from tests.api.helpers import error_fields

pytestmark = pytest.mark.django_db

URL = "/api/v1/searches/run-chunk"


@pytest.fixture
def wikimedia(respx_mock, settings):
    return respx_mock.get(url__startswith=settings.WIKIMEDIA["base_url"])


def test_it_runs_a_chunk_and_reports_outcomes(client, acting_as, make_import, make_search, wikimedia):
    wikimedia.mock(return_value=httpx.Response(200, json={"query": {"pages": []}}))
    user = acting_as()
    csv_import = make_import(user)
    search = make_search(user, csv_import=csv_import, status=CarSearch.Status.PENDING)

    response = client.post(URL, {"csv_import_id": csv_import.id}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["outcomes", "ran_seconds", "remaining", "blocked"]
    assert body["remaining"] == 0
    assert body["blocked"] is None
    assert body["outcomes"] == [
        {"id": search.id, "make": "Toyota", "model": "RAV4", "from_year": 1997, "outcome": "completed"}
    ]


def test_it_reports_a_block_with_its_retry_window(client, acting_as, make_import, make_search, wikimedia):
    wikimedia.mock(return_value=httpx.Response(429, text="Too Many Requests", headers={"Retry-After": "600"}))
    user = acting_as()
    csv_import = make_import(user)
    make_search(user, csv_import=csv_import, status=CarSearch.Status.PENDING)

    body = client.post(URL, {"csv_import_id": csv_import.id}, format="json").json()

    assert body["blocked"] == {"status": 429, "retry_after_seconds": 600}


def test_a_finished_import_returns_an_empty_success(client, acting_as, make_import):
    user = acting_as()
    csv_import = make_import(user)

    response = client.post(URL, {"csv_import_id": csv_import.id}, format="json")

    assert response.status_code == 200
    assert response.json()["remaining"] == 0
    assert response.json()["outcomes"] == []


def test_running_requires_the_search_run_ability(client, acting_as, make_import, make_search):
    user = acting_as([abilities.SEARCH_READ])
    csv_import = make_import(user)
    search = make_search(user, csv_import=csv_import, status=CarSearch.Status.PENDING)

    assert client.post(URL, {"csv_import_id": csv_import.id}, format="json").status_code == 403
    search.refresh_from_db()
    assert search.status == CarSearch.Status.PENDING


@pytest.mark.parametrize("body", [{"csv_import_id": 9999}, {}, {"csv_import_id": "abc"}])
def test_it_requires_an_existing_import(client, acting_as, body):
    acting_as()

    assert error_fields(client.post(URL, body, format="json")) == {"csv_import_id"}


def test_running_requires_authentication(client):
    assert client.post(URL, {"csv_import_id": 1}, format="json").status_code == 401


def test_any_authenticated_user_may_run_any_import(client, acting_as, make_import, make_search, wikimedia):
    """
    There is no ownership model: `imported_by` records who uploaded, not who
    owns, and every read endpoint already shows every import. If ownership
    arrives, this test should fail and be changed deliberately.
    """
    wikimedia.mock(return_value=httpx.Response(200, json={"query": {"pages": []}}))
    csv_import = make_import()
    search = make_search(csv_import=csv_import, status=CarSearch.Status.PENDING)
    acting_as()

    assert client.post(URL, {"csv_import_id": csv_import.id}, format="json").status_code == 200
    search.refresh_from_db()
    assert search.status == CarSearch.Status.COMPLETED


def test_the_chunk_is_scoped_to_the_named_import(client, acting_as, make_import):
    acting_as()
    csv_import = make_import()

    with mock.patch("api.v1.views.searches.run_chunk", return_value=ChunkResult()) as run_chunk:
        client.post(URL, {"csv_import_id": csv_import.id}, format="json")

    run_chunk.assert_called_once_with(csv_import.id)
