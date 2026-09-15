import pytest

ORIGIN = "https://cars-images.netlify.app"


def preflight(client, origin: str):
    return client.options("/api/v1/auth/me", HTTP_ORIGIN=origin, HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET")


@pytest.fixture
def allowed_origin(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


def test_nothing_is_allowed_until_an_origin_is_configured(client, settings):
    settings.CORS_ALLOWED_ORIGINS = []

    assert "Access-Control-Allow-Origin" not in preflight(client, ORIGIN)


def test_the_configured_origin_gets_cors_headers(client, allowed_origin):
    response = preflight(client, ORIGIN)

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ORIGIN
    assert "authorization" in response["Access-Control-Allow-Headers"]


def test_any_other_origin_is_never_echoed_back(client, allowed_origin):
    assert "Access-Control-Allow-Origin" not in preflight(client, "https://evil.example")


@pytest.mark.django_db
def test_an_actual_request_from_the_configured_origin_is_allowed(client, allowed_origin):
    response = client.get("/api/v1/auth/me", HTTP_ORIGIN=ORIGIN)

    assert response.status_code == 401
    assert response["Access-Control-Allow-Origin"] == ORIGIN


def test_cors_is_limited_to_the_api(client, allowed_origin):
    assert "Access-Control-Allow-Origin" not in client.options(
        "/exports/download", HTTP_ORIGIN=ORIGIN, HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET"
    )
