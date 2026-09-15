import pytest
from rest_framework.test import APIClient

from tests.factories import issue_token

pytestmark = pytest.mark.django_db


def test_html_only_accept_header_still_gets_json_401():
    response = APIClient().get("/api/v1/auth/me", HTTP_ACCEPT="text/html")
    assert response.status_code == 401
    assert response["Content-Type"].startswith("application/json")
    assert response.json() == {"message": "Unauthenticated."}


def test_throttle_rates_are_read_from_settings_per_request(settings):
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "read": "2/min"},
    }
    _, token = issue_token()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    statuses = [client.get("/api/v1/auth/me").status_code for _ in range(3)]
    assert statuses == [200, 200, 429]


def test_site_root_redirects_to_admin(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/"
