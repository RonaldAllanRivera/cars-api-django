import pytest

from apps.accounts import abilities
from apps.searches.models import CarSearch
from tests.api.helpers import error_fields, ids

pytestmark = pytest.mark.django_db

SEARCH_FIELDS = [
    "id",
    "make",
    "model",
    "commons_category",
    "from_year",
    "to_year",
    "color",
    "transmission",
    "transparent_background",
    "images_per_year",
    "status",
    "csv_import_id",
    "requested_by",
    "images_count",
    "created_at",
    "updated_at",
]


def test_listing_requires_the_search_read_ability(client, acting_as):
    assert client.get("/api/v1/searches").status_code == 401

    acting_as([abilities.REVIEW_WRITE])
    assert client.get("/api/v1/searches").status_code == 403


def test_the_list_is_newest_first_with_image_counts(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    older = make_search(user)
    newer = make_search(user, make="Honda", model="Civic")
    make_image(older)
    make_image(older)

    body = client.get("/api/v1/searches").json()

    assert [row["id"] for row in body["data"]] == [newer.id, older.id]
    assert [row["images_count"] for row in body["data"]] == [0, 2]
    assert {"next_cursor", "prev_cursor", "per_page"} <= set(body["meta"])


def test_the_list_filters_by_status_and_rejects_unknown_statuses(client, acting_as, make_search):
    user = acting_as([abilities.SEARCH_READ])
    failed = make_search(user, status=CarSearch.Status.FAILED)
    make_search(user, status=CarSearch.Status.COMPLETED)

    assert ids(client.get("/api/v1/searches?status=failed")) == [failed.id]
    assert error_fields(client.get("/api/v1/searches?status=exploded")) == {"status"}


def test_show_returns_the_search_with_its_image_count(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    search = make_search(user, commons_category="Toyota RAV4 (XA10)")
    make_image(search)

    response = client.get(f"/api/v1/searches/{search.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert list(data) == SEARCH_FIELDS
    assert (data["id"], data["commons_category"], data["images_count"]) == (search.id, "Toyota RAV4 (XA10)", 1)
    assert data["requested_by"] == user.id
    assert client.get("/api/v1/searches/999999").status_code == 404


def test_a_searchs_images_are_scoped_to_it_and_filterable(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    mine = make_search(user)
    other = make_search(user, make="Honda", model="Civic")
    approved = make_image(mine, review_status="approved")
    pending = make_image(mine)
    make_image(other, review_status="approved")

    assert ids(client.get(f"/api/v1/searches/{mine.id}/images")) == [pending.id, approved.id]
    assert ids(client.get(f"/api/v1/searches/{mine.id}/images?review_status=approved")) == [approved.id]
    assert error_fields(client.get(f"/api/v1/searches/{mine.id}/images?review_status=meh")) == {"review_status"}
    assert client.get("/api/v1/searches/999999/images").status_code == 404


def test_a_searchs_images_page_links_back_to_the_nested_path(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    search = make_search(user)
    make_image(search)
    make_image(search)

    body = client.get(f"/api/v1/searches/{search.id}/images?per_page=1", SERVER_NAME="localhost").json()

    assert body["meta"]["path"] == f"http://localhost/api/v1/searches/{search.id}/images"
    assert body["links"]["next"].startswith(f"http://localhost/api/v1/searches/{search.id}/images?per_page=1&cursor=")


@pytest.mark.parametrize(("source", "csv_derived"), [("csv", True), ("adhoc", False)])
def test_it_filters_by_source(client, acting_as, make_search, make_import, source, csv_derived):
    user = acting_as()
    from_csv = make_search(user, csv_import=make_import())
    ad_hoc = make_search(user, csv_import=None)

    assert ids(client.get(f"/api/v1/searches?source={source}")) == [from_csv.id if csv_derived else ad_hoc.id]


def test_it_filters_by_import(client, acting_as, make_search, make_import):
    user = acting_as()
    mine, theirs = make_import(), make_import()
    wanted = make_search(user, csv_import=mine)
    make_search(user, csv_import=theirs)

    assert ids(client.get(f"/api/v1/searches?csv_import_id={mine.id}")) == [wanted.id]
    assert error_fields(client.get("/api/v1/searches?csv_import_id=999999")) == {"csv_import_id"}


def test_coverage_no_images_finds_searches_that_ran_and_found_nothing(client, acting_as, make_search, make_image):
    user = acting_as()
    make_image(make_search(user, status=CarSearch.Status.COMPLETED))
    empty = make_search(user, status=CarSearch.Status.COMPLETED)
    make_search(user, status=CarSearch.Status.PENDING)

    assert ids(client.get("/api/v1/searches?coverage=no_images")) == [empty.id]


def test_coverage_with_images_finds_searches_with_any_image(client, acting_as, make_search, make_image):
    user = acting_as()
    found = make_search(user)
    make_image(found)
    make_image(found)
    make_search(user)

    response = client.get("/api/v1/searches?coverage=with_images")

    assert ids(response) == [found.id]
    assert response.json()["data"][0]["images_count"] == 2


def test_coverage_not_run_includes_running(client, acting_as, make_search):
    user = acting_as()
    pending = make_search(user, status=CarSearch.Status.PENDING)
    running = make_search(user, status=CarSearch.Status.RUNNING)
    make_search(user, status=CarSearch.Status.COMPLETED)

    assert ids(client.get("/api/v1/searches?coverage=not_run")) == [running.id, pending.id]


def test_an_unfiltered_list_still_returns_everything(client, acting_as, make_search, make_import):
    user = acting_as()
    make_search(user, csv_import=make_import())
    make_search(user, csv_import=None)

    assert len(client.get("/api/v1/searches").json()["data"]) == 2


def test_it_rejects_an_unknown_coverage_value(client, acting_as):
    acting_as()

    assert error_fields(client.get("/api/v1/searches?coverage=maybe")) == {"coverage"}
