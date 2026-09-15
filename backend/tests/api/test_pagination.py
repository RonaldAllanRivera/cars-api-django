import base64
import json

import pytest

from api.pagination import Cursor
from apps.accounts import abilities
from tests.api.helpers import ids

pytestmark = pytest.mark.django_db


def test_the_cursor_is_laravels_wire_format():
    cursor = Cursor({"id": 2}, points_to_next=True)

    assert cursor.encode() == "eyJpZCI6MiwiX3BvaW50c1RvTmV4dEl0ZW1zIjp0cnVlfQ"
    assert Cursor.decode(cursor.encode()) == cursor


@pytest.mark.parametrize("garbage", ["not-a-cursor", "!!!", base64.urlsafe_b64encode(b"[1,2]").decode()])
def test_a_malformed_cursor_reads_as_the_first_page(client, acting_as, make_search, make_image, garbage):
    search = make_search(acting_as([abilities.SEARCH_READ]))
    newest = make_image(search)

    response = client.get(f"/api/v1/images?cursor={garbage}")

    assert response.status_code == 200
    assert ids(response) == [newest.id]


def test_a_cursor_for_another_ordering_reads_as_the_first_page(client, acting_as):
    acting_as([abilities.ERRORS_READ])
    foreign = Cursor({"id": 5}, points_to_next=True).encode()

    assert client.get(f"/api/v1/errors?cursor={foreign}").status_code == 200


def test_next_and_previous_cursors_walk_the_list_both_ways(client, acting_as, make_search, make_image):
    search = make_search(acting_as([abilities.SEARCH_READ]))
    images = [make_image(search) for _ in range(5)]
    newest_first = [image.id for image in reversed(images)]

    first = client.get("/api/v1/images?per_page=2").json()
    assert first["meta"]["prev_cursor"] is None
    second = client.get(f"/api/v1/images?per_page=2&cursor={first['meta']['next_cursor']}").json()
    third = client.get(f"/api/v1/images?per_page=2&cursor={second['meta']['next_cursor']}").json()

    assert [row["id"] for row in second["data"]] == newest_first[2:4]
    assert [row["id"] for row in third["data"]] == newest_first[4:]
    assert third["meta"]["next_cursor"] is None

    back = client.get(f"/api/v1/images?per_page=2&cursor={third['meta']['prev_cursor']}").json()
    assert [row["id"] for row in back["data"]] == newest_first[2:4]
    assert back["meta"]["next_cursor"] is not None

    start = client.get(f"/api/v1/images?per_page=2&cursor={back['meta']['prev_cursor']}").json()
    assert [row["id"] for row in start["data"]] == newest_first[:2]
    assert start["meta"]["prev_cursor"] is None


def test_links_keep_the_query_string_and_replace_the_cursor(client, acting_as, make_search, make_image):
    search = make_search(acting_as([abilities.SEARCH_READ]))
    for _ in range(3):
        make_image(search, review_status="pending")

    first = client.get("/api/v1/images?review_status=pending&per_page=1", SERVER_NAME="localhost").json()
    next_cursor = first["meta"]["next_cursor"]
    assert first["links"]["next"] == (
        f"http://localhost/api/v1/images?review_status=pending&per_page=1&cursor={next_cursor}"
    )

    second = client.get(first["links"]["next"], SERVER_NAME="localhost").json()
    assert second["links"]["next"] == (
        f"http://localhost/api/v1/images?review_status=pending&per_page=1&cursor={second['meta']['next_cursor']}"
    )
    decoded = json.loads(base64.urlsafe_b64decode(second["meta"]["prev_cursor"] + "=="))
    assert decoded["_pointsToNextItems"] is False
