import pytest

from apps.accounts import abilities
from apps.accounts.models import ApiToken
from tests.api.helpers import error_fields
from tests.factories import UserFactory, issue_token

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login"
LOGIN = {"email": "allan@example.com", "password": "password", "device_name": "Pixel 8"}


@pytest.fixture
def allan():
    return UserFactory(email="allan@example.com")


def test_login_returns_a_scoped_bearer_token(client, allan):
    response = client.post(LOGIN_URL, LOGIN, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["abilities"] == abilities.DEFAULT
    assert body["user"] == {"id": allan.id, "name": allan.name, "email": "allan@example.com"}
    token = ApiToken.objects.get(user=allan)
    assert token.name == "Pixel 8"
    assert token.abilities == abilities.DEFAULT
    assert body["token"].startswith(f"{token.pk}|")


def test_login_rejects_a_wrong_password_without_issuing_a_token(client, allan):
    response = client.post(LOGIN_URL, {**LOGIN, "password": "wrong"}, format="json")

    assert error_fields(response) == {"email"}
    assert not ApiToken.objects.exists()


def test_an_unknown_email_gets_the_same_answer_as_a_wrong_password(client, allan):
    wrong_password = client.post(LOGIN_URL, {**LOGIN, "password": "wrong"}, format="json")
    unknown_email = client.post(LOGIN_URL, {**LOGIN, "email": "nobody@example.com"}, format="json")

    assert unknown_email.status_code == wrong_password.status_code == 422
    assert unknown_email.json() == wrong_password.json()


def test_login_requires_a_device_name(client):
    response = client.post(LOGIN_URL, {"email": "a@b.co", "password": "x"}, format="json")

    assert "device_name" in error_fields(response)


def test_login_ignores_a_stale_bearer_header(client, allan):
    client.credentials(HTTP_AUTHORIZATION="Bearer 999|revoked")

    assert client.post(LOGIN_URL, LOGIN, format="json").status_code == 201


def test_login_is_throttled_after_five_attempts(client, allan, throttle_rate):
    throttle_rate("login", "5/min")
    bad = {**LOGIN, "password": "wrong"}

    for _ in range(5):
        assert client.post(LOGIN_URL, bad, format="json").status_code == 422

    response = client.post(LOGIN_URL, bad, format="json")
    assert response.status_code == 429
    assert response.json() == {"message": "Too Many Attempts."}


def test_me_requires_a_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"message": "Unauthenticated."}


@pytest.mark.parametrize("accept", [None, "text/html,application/xhtml+xml,*/*;q=0.8"], ids=["none", "browser"])
def test_a_request_without_a_json_accept_header_still_gets_a_json_401(client, accept):
    headers = {"HTTP_ACCEPT": accept} if accept else {}

    response = client.get("/api/v1/auth/me", **headers)

    assert response.status_code == 401
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"message": "Unauthenticated."}


def test_me_returns_the_user_behind_a_real_bearer_token(client, acting_as):
    user = acting_as()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {"data": {"id": user.id, "name": user.name, "email": user.email}}


def test_logout_revokes_only_the_calling_token(client):
    user, phone = issue_token()
    _, laptop = issue_token(user)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {phone}")
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert response.content == b""

    assert client.get("/api/v1/auth/me").status_code == 401
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {laptop}")
    assert client.get("/api/v1/auth/me").status_code == 200
    assert user.api_tokens.count() == 1


def test_the_default_scope_is_a_strict_subset_of_every_ability():
    assert abilities.DEFAULT != abilities.ALL
    assert set(abilities.DEFAULT) < set(abilities.ALL)


def test_the_privileged_abilities_are_not_issued_by_default():
    privileged = [abilities.IMPORTS_READ, abilities.IMPORTS_WRITE, abilities.SEARCH_RUN, abilities.EXPORTS_READ]

    for ability in privileged:
        assert ability in abilities.ALL
        assert ability not in abilities.DEFAULT


@pytest.mark.parametrize(
    ("requested", "granted"),
    [
        pytest.param(
            [abilities.SEARCH_READ, abilities.REVIEW_WRITE],
            [abilities.SEARCH_READ, abilities.REVIEW_WRITE],
            id="exact-subset",
        ),
        pytest.param(
            [abilities.SEARCH_READ, abilities.SEARCH_RUN],
            [abilities.SEARCH_READ, abilities.SEARCH_RUN],
            id="privileged-when-asked",
        ),
        pytest.param(
            [abilities.REVIEW_WRITE, abilities.SEARCH_READ, abilities.REVIEW_WRITE],
            [abilities.SEARCH_READ, abilities.REVIEW_WRITE],
            id="canonical-order-and-deduplicated",
        ),
        pytest.param(
            [abilities.EXPORTS_READ, abilities.ERRORS_READ],
            [abilities.ERRORS_READ, abilities.EXPORTS_READ],
            id="reported-matches-stored",
        ),
    ],
)
def test_login_issues_the_requested_abilities_in_canonical_order(client, allan, requested, granted):
    response = client.post(LOGIN_URL, {**LOGIN, "abilities": requested}, format="json")

    assert response.status_code == 201
    assert response.json()["abilities"] == granted
    assert ApiToken.objects.get(user=allan).abilities == granted


def test_login_rejects_an_unknown_ability(client, allan):
    response = client.post(LOGIN_URL, {**LOGIN, "abilities": ["search:reed"]}, format="json")

    assert error_fields(response) == {"abilities.0"}
    assert not ApiToken.objects.exists()


def test_login_rejects_an_empty_abilities_array(client, allan):
    response = client.post(LOGIN_URL, {**LOGIN, "abilities": []}, format="json")

    assert error_fields(response) == {"abilities"}
    assert not ApiToken.objects.exists()


def test_an_expired_token_is_unauthenticated(client, acting_as):
    user = acting_as()
    ApiToken.objects.filter(user=user).update(expires_at="2000-01-01T00:00:00Z")

    assert client.get("/api/v1/auth/me").status_code == 401


def test_an_unknown_api_route_is_a_json_404(client):
    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json() == {"message": "Not found."}
