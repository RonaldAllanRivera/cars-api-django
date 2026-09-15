import pytest

from apps.accounts import abilities
from apps.images.models import CarImage
from tests.api.helpers import error_fields

pytestmark = pytest.mark.django_db


def review_url(image_id: int) -> str:
    return f"/api/v1/images/{image_id}/review"


def test_reviewing_requires_the_review_write_ability(client, acting_as, make_search, make_image):
    user = acting_as([abilities.SEARCH_WRITE])
    image = make_image(make_search(user))

    assert client.patch(review_url(image.id), {"review_status": "approved"}, format="json").status_code == 403


def test_approving_stamps_the_reviewer_and_leaves_the_machine_verdict_alone(
    client, acting_as, make_search, make_image, time_machine
):
    time_machine.move_to("2026-01-15T09:00:00Z", tick=False)
    user = acting_as([abilities.REVIEW_WRITE])
    image = make_image(make_search(user), make_confirmed=False, year_confirmed=False)

    response = client.patch(review_url(image.id), {"review_status": "approved"}, format="json")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["review_status"] == "approved"
    assert data["reviewed_by"] == user.id
    assert data["reviewed_at"] == "2026-01-15T09:00:00+00:00"
    assert data["make_confirmed"] is False
    image.refresh_from_db()
    assert image.review_status == CarImage.ReviewStatus.APPROVED
    assert image.reviewed_by == user
    assert image.reviewed_at is not None
    assert image.make_confirmed is False, "the human verdict must not overwrite the machine one"
    assert image.year_confirmed is False


def test_rejecting_works_the_same_way(client, acting_as, make_search, make_image):
    user = acting_as([abilities.REVIEW_WRITE])
    image = make_image(make_search(user))

    data = client.patch(review_url(image.id), {"review_status": "rejected"}, format="json").json()["data"]

    assert data["review_status"] == "rejected"
    assert data["reviewed_by"] == user.id


def test_returning_to_pending_clears_the_reviewer(client, acting_as, make_search, make_image):
    user = acting_as([abilities.REVIEW_WRITE])
    image = make_image(
        make_search(user),
        review_status=CarImage.ReviewStatus.APPROVED,
        reviewed_by=user,
        reviewed_at="2026-01-15T09:00:00Z",
    )

    response = client.patch(review_url(image.id), {"review_status": "pending"}, format="json")

    data = response.json()["data"]
    assert (data["review_status"], data["reviewed_by"], data["reviewed_at"]) == ("pending", None, None)


@pytest.mark.parametrize("body", [{"review_status": "meh"}, {}], ids=["unknown", "missing"])
def test_an_unknown_status_is_rejected(client, acting_as, make_search, make_image, body):
    user = acting_as([abilities.REVIEW_WRITE])
    image = make_image(make_search(user))

    assert error_fields(client.patch(review_url(image.id), body, format="json")) == {"review_status"}
    image.refresh_from_db()
    assert image.review_status == CarImage.ReviewStatus.PENDING


def test_an_unknown_image_404s(client, acting_as):
    acting_as([abilities.REVIEW_WRITE])

    assert client.patch(review_url(999999), {"review_status": "approved"}, format="json").status_code == 404
