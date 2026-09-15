import pytest

from apps.accounts import abilities
from apps.images.models import CarImage
from tests.api.helpers import error_fields, ids

pytestmark = pytest.mark.django_db

IMAGE_FIELDS = [
    "id",
    "car_search_id",
    "make",
    "model",
    "year",
    "color",
    "title",
    "description",
    "source_url",
    "thumbnail_url",
    "width",
    "height",
    "license",
    "attribution",
    "make_confirmed",
    "year_confirmed",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "download_status",
    "created_at",
]


def test_listing_requires_a_token(client):
    assert client.get("/api/v1/images").status_code == 401


def test_listing_requires_the_search_read_ability(client, acting_as):
    acting_as([abilities.ERRORS_READ])

    response = client.get("/api/v1/images")

    assert response.status_code == 403
    assert response.json() == {"message": "Invalid ability provided."}


def test_the_list_is_cursor_paginated_newest_first(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    search = make_search(user)
    a, b, c = make_image(search), make_image(search), make_image(search)

    first = client.get("/api/v1/images?per_page=2")
    assert first.status_code == 200
    assert ids(first) == [c.id, b.id]
    cursor = first.json()["meta"]["next_cursor"]
    assert cursor is not None

    second = client.get(f"/api/v1/images?per_page=2&cursor={cursor}")
    assert ids(second) == [a.id]
    assert second.json()["meta"]["next_cursor"] is None


def test_each_filter_narrows_the_list(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    toyota = make_search(user)
    honda = make_search(user, make="Honda", model="Civic", from_year=2010, to_year=2010)
    hit = make_image(
        toyota,
        make_confirmed=True,
        year_confirmed=True,
        review_status=CarImage.ReviewStatus.APPROVED,
        download_status=CarImage.DownloadStatus.DOWNLOADED,
    )
    miss = make_image(
        honda,
        make_confirmed=False,
        year_confirmed=False,
        review_status=CarImage.ReviewStatus.REJECTED,
        download_status=CarImage.DownloadStatus.FAILED,
    )
    # Neither confirmed nor denied: a boolean filter must never match it.
    make_image(honda)

    for query in [
        "make=Toyota",
        "model=RAV4",
        "year=1997",
        "make_confirmed=1",
        "year_confirmed=true",
        "make_confirmed=true",
        "year_confirmed=1",
        "review_status=approved",
        "download_status=downloaded",
    ]:
        assert ids(client.get(f"/api/v1/images?{query}")) == [hit.id], query

    for query in ["make_confirmed=0", "year_confirmed=false"]:
        assert ids(client.get(f"/api/v1/images?{query}")) == [miss.id], f"{query} must exclude the null verdict"


def test_an_invalid_filter_is_rejected(client, acting_as):
    acting_as([abilities.SEARCH_READ])

    assert error_fields(client.get("/api/v1/images?review_status=maybe")) == {"review_status"}
    assert error_fields(client.get("/api/v1/images?year=1899")) == {"year"}
    assert error_fields(client.get("/api/v1/images?year=abc")) == {"year"}


@pytest.mark.parametrize("per_page", ["0", "101", "500", "abc", ""])
def test_per_page_outside_1_to_100_is_rejected(client, acting_as, per_page):
    acting_as([abilities.SEARCH_READ])

    assert error_fields(client.get(f"/api/v1/images?per_page={per_page}")) == {"per_page"}


def test_a_year_filter_may_run_one_year_ahead(client, acting_as, time_machine):
    time_machine.move_to("2026-06-01T00:00:00Z")
    acting_as([abilities.SEARCH_READ])

    assert client.get("/api/v1/images?year=2027").status_code == 200
    assert error_fields(client.get("/api/v1/images?year=2028")) == {"year"}


@pytest.mark.parametrize(
    "query", ["make_confirmed=maybe", "make_confirmed=yes", "make_confirmed=", "year_confirmed=on"]
)
def test_boolean_filters_accept_only_true_false_and_1_0(client, acting_as, query):
    acting_as([abilities.SEARCH_READ])

    assert error_fields(client.get(f"/api/v1/images?{query}")) == {query.split("=")[0]}


def test_a_sent_but_blank_filter_is_rejected_rather_than_ignored(client, acting_as):
    acting_as([abilities.SEARCH_READ])

    assert error_fields(client.get("/api/v1/images?make=&review_status=")) == {"make", "review_status"}


def test_show_returns_the_full_record(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    image = make_image(
        make_search(user),
        license="CC BY-SA 4.0",
        attribution="Photo by Example",
        make_confirmed=True,
        review_status=CarImage.ReviewStatus.APPROVED,
        reviewed_by=user,
        reviewed_at="2026-01-15T09:00:00Z",
    )

    response = client.get(f"/api/v1/images/{image.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert list(data) == IMAGE_FIELDS
    assert data["id"] == image.id
    assert data["license"] == "CC BY-SA 4.0"
    assert data["attribution"] == "Photo by Example"
    assert data["make_confirmed"] is True
    assert data["year_confirmed"] is None
    assert data["review_status"] == "approved"
    assert data["reviewed_by"] == user.id
    assert data["reviewed_at"] == "2026-01-15T09:00:00+00:00"


def test_show_ignores_list_filters(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_READ])
    image = make_image(make_search(user))

    assert client.get(f"/api/v1/images/{image.id}?make=Honda").status_code == 200


def test_show_404s_for_an_unknown_image(client, acting_as):
    acting_as([abilities.SEARCH_READ])

    response = client.get("/api/v1/images/999999")

    assert response.status_code == 404
    assert set(response.json()) == {"message"}


def test_it_filters_images_by_csv_import(client, acting_as, make_search, make_import, make_image):
    user = acting_as()
    mine, theirs = make_import(user), make_import(user)
    wanted = make_image(make_search(user, csv_import=mine))
    make_image(make_search(user, csv_import=theirs))

    assert ids(client.get(f"/api/v1/images?csv_import_id={mine.id}")) == [wanted.id]


def test_an_unknown_csv_import_is_rejected(client, acting_as):
    acting_as()

    assert error_fields(client.get("/api/v1/images?csv_import_id=999999")) == {"csv_import_id"}


def test_the_count_agrees_with_the_list_for_the_same_filters(client, acting_as, make_search, make_import, make_image):
    user = acting_as()
    csv_import = make_import(user)
    search = make_search(user, csv_import=csv_import)
    make_image(search, make_confirmed=True)
    make_image(search, make_confirmed=True)
    make_image(search, make_confirmed=False)
    query = f"csv_import_id={csv_import.id}&make_confirmed=1"

    listed = client.get(f"/api/v1/images?{query}&per_page=100").json()["data"]
    response = client.get(f"/api/v1/images/count?{query}")

    assert response.status_code == 200
    assert response.json() == {"count": 2}
    assert len(listed) == 2


def test_count_is_not_captured_as_an_image_id(client, acting_as):
    acting_as()

    response = client.get("/api/v1/images/count")

    assert response.status_code == 200
    assert response.json() == {"count": 0}


def test_counting_requires_search_read(client, acting_as):
    acting_as([abilities.REVIEW_WRITE])

    assert client.get("/api/v1/images/count").status_code == 403


def test_the_list_runs_a_constant_number_of_queries(
    client, acting_as, make_search, make_image, django_assert_max_num_queries
):
    user = acting_as([abilities.SEARCH_READ])
    for _ in range(3):
        make_image(make_search(user), reviewed_by=user)

    # Token lookup, last_used_at update, the page - however many rows there are.
    with django_assert_max_num_queries(3):
        assert client.get("/api/v1/images").status_code == 200
