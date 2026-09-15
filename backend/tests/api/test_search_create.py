from unittest import mock

import httpx
import pytest

from apps.accounts import abilities
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch, WikimediaBlockEvent
from tests.api.helpers import error_fields

pytestmark = pytest.mark.django_db

URL = "/api/v1/searches"
PAYLOAD = {"make": "Toyota", "model": "RAV4", "from_year": 1997, "to_year": 1997, "images_per_year": 5}


@pytest.fixture
def wikimedia(respx_mock, settings):
    """Every Commons call answered by one route the test configures."""
    return respx_mock.get(url__startswith=settings.WIKIMEDIA["base_url"])


@pytest.fixture
def empty_wikimedia(wikimedia):
    return wikimedia.mock(return_value=httpx.Response(200, json={"query": {"pages": []}}))


def test_creating_requires_the_search_write_ability(client, acting_as):
    assert client.post(URL, PAYLOAD, format="json").status_code == 401

    acting_as([abilities.SEARCH_READ])
    assert client.post(URL, PAYLOAD, format="json").status_code == 403


def test_a_year_span_wider_than_the_cap_is_rejected(client, acting_as, empty_wikimedia):
    acting_as([abilities.SEARCH_WRITE])

    response = client.post(URL, {**PAYLOAD, "from_year": 2018, "to_year": 2022}, format="json")
    assert error_fields(response) == {"to_year"}
    assert response.json()["message"] == (
        "The year range may span at most 3 years, because the search runs inside this request."
    )

    # Three years apart (four inclusive) is the widest allowed.
    assert client.post(URL, {**PAYLOAD, "from_year": 2018, "to_year": 2021}, format="json").status_code == 201


def test_the_span_cap_is_configurable(client, acting_as, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "api_search_max_year_span": 1}
    acting_as([abilities.SEARCH_WRITE])

    response = client.post(URL, {**PAYLOAD, "from_year": 2018, "to_year": 2020}, format="json")

    assert response.json()["errors"]["to_year"] == [
        "The year range may span at most 1 years, because the search runs inside this request."
    ]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"images_per_year": 6}, "images_per_year"),
        ({"images_per_year": 0}, "images_per_year"),
        ({"from_year": 1899}, "from_year"),
        ({"to_year": 2099}, "to_year"),
        ({"make": ""}, "make"),
        ({"transparent_background": "yes"}, "transparent_background"),
    ],
)
def test_out_of_bounds_fields_are_rejected(client, acting_as, overrides, field):
    acting_as([abilities.SEARCH_WRITE])

    assert field in error_fields(client.post(URL, {**PAYLOAD, **overrides}, format="json"))


def test_a_non_integer_year_gets_only_the_integer_error(client, acting_as):
    acting_as([abilities.SEARCH_WRITE])

    response = client.post(URL, {**PAYLOAD, "from_year": "abc"}, format="json")

    assert error_fields(response) == {"from_year"}, "the span rule must not run on a year that failed validation"


def test_a_search_is_created_run_inline_and_returned_completed(client, acting_as, empty_wikimedia):
    user = acting_as([abilities.SEARCH_WRITE])

    response = client.post(URL, PAYLOAD, format="json")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["make"] == "Toyota"
    assert data["requested_by"] == user.id
    assert data["images_count"] == 0
    assert data["images"] == []


def test_images_per_year_defaults_to_the_cap(client, acting_as, empty_wikimedia):
    acting_as([abilities.SEARCH_WRITE])
    payload = {key: value for key, value in PAYLOAD.items() if key != "images_per_year"}

    assert client.post(URL, payload, format="json").json()["data"]["images_per_year"] == 5


def test_reversed_years_are_stored_in_order(client, acting_as, empty_wikimedia):
    acting_as([abilities.SEARCH_WRITE])

    data = client.post(URL, {**PAYLOAD, "from_year": 1999, "to_year": 1997}, format="json").json()["data"]

    assert (data["from_year"], data["to_year"]) == (1997, 1999)


def test_an_identical_completed_search_is_returned_without_touching_wikimedia(
    client, acting_as, make_search, wikimedia
):
    user = acting_as([abilities.SEARCH_WRITE])
    existing = make_search(user)  # Toyota RAV4 1997, 5/yr, completed

    response = client.post(URL, PAYLOAD, format="json")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == existing.id
    assert not wikimedia.called
    assert CarSearch.objects.count() == 1


def test_a_wikimedia_block_answers_503_with_retry_after(client, acting_as, wikimedia):
    acting_as([abilities.SEARCH_WRITE])
    wikimedia.mock(return_value=httpx.Response(429, text="Rate limit exceeded", headers={"Retry-After": "120"}))

    response = client.post(URL, PAYLOAD, format="json")

    assert response.status_code == 503
    assert response["Retry-After"] == "120"
    body = response.json()
    assert body["message"] == "Wikimedia is rate-limiting this server. Try again later."
    assert body["retry_after_seconds"] == 120
    assert body["data"]["status"] == "failed"
    assert WikimediaBlockEvent.objects.count() == 1
    assert ErrorEvent.objects.filter(context=ErrorEvent.Context.WIKIMEDIA_BLOCK).count() == 1


def test_a_block_without_a_retry_window_sends_no_retry_after_header(client, acting_as):
    from apps.searches.services.wikimedia import WikimediaBlockedError

    acting_as([abilities.SEARCH_WRITE])
    with mock.patch("api.v1.views.searches.run_search_query", side_effect=WikimediaBlockedError(403)):
        response = client.post(URL, PAYLOAD, format="json")

    assert response.status_code == 503
    assert "Retry-After" not in response
    assert response.json()["retry_after_seconds"] is None


def test_any_other_failure_answers_502_and_is_logged(client, acting_as, wikimedia):
    acting_as([abilities.SEARCH_WRITE])
    wikimedia.mock(return_value=httpx.Response(500, text="Internal server error"))

    response = client.post(URL, PAYLOAD, format="json")

    assert response.status_code == 502
    assert response.json()["message"] == "The search failed. The reason is in the error log."
    assert response.json()["data"]["status"] == "failed"
    assert WikimediaBlockEvent.objects.count() == 0
    assert ErrorEvent.objects.filter(context=ErrorEvent.Context.SEARCH_RUN).count() == 1


def test_creation_is_throttled_to_ten_per_minute(client, acting_as, empty_wikimedia, throttle_rate):
    throttle_rate("write", "10/min")
    acting_as([abilities.SEARCH_WRITE])

    # The first creates; the next nine hit the dedupe path. All ten count.
    for _ in range(10):
        assert client.post(URL, PAYLOAD, format="json").status_code in (200, 201)

    assert client.post(URL, PAYLOAD, format="json").status_code == 429
