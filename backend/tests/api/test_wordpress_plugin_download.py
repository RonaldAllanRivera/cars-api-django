import io
import zipfile
from urllib.parse import urlsplit

import pytest

from apps.accounts import abilities
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login"
LINK_URL = "/api/v1/wordpress-plugin/download-link"


def login(client, user, requested):
    body = {"email": user.email, "password": "password", "device_name": "web", "abilities": requested}
    return client.post(LOGIN_URL, body, format="json").json()["abilities"]


class TestBlogAbilitiesAreStaffOnly:
    def test_a_non_staff_account_is_not_granted_blog_abilities_even_when_it_asks(self, client):
        """They spend AI budget and hand out the plugin; asking for them is not enough."""
        user = UserFactory()

        granted = login(client, user, [abilities.SEARCH_READ, abilities.BLOG_WRITE, abilities.BLOG_PUBLISH])

        assert granted == [abilities.SEARCH_READ]

    def test_a_staff_account_is_granted_them(self, client):
        staff = UserFactory(is_staff=True)

        granted = login(client, staff, [abilities.SEARCH_READ, abilities.BLOG_WRITE])

        assert granted == [abilities.SEARCH_READ, abilities.BLOG_WRITE]

    def test_other_privileged_abilities_are_unchanged_for_non_staff(self, client):
        assert login(client, UserFactory(), [abilities.SEARCH_RUN]) == [abilities.SEARCH_RUN]


class TestDownloadLink:
    def test_staff_get_a_signed_link_to_the_current_version(self, client, acting_as):
        acting_as([abilities.BLOG_WRITE], user=UserFactory(is_staff=True))

        response = client.post(LINK_URL, format="json")

        body = response.json()
        assert response.status_code == 200
        assert urlsplit(body["url"]).path == "/downloads/wordpress-plugin"
        assert (body["filename"], body["version"]) == ("cars-images-publisher-1.0.0.zip", "1.0.0")
        assert body["expires_at"]

    def test_a_token_with_the_ability_but_no_staff_account_is_refused(self, client, acting_as):
        """A token minted before the staff-only rule, or by hand, must not be enough on its own."""
        acting_as([abilities.BLOG_WRITE], user=UserFactory(is_staff=False))

        assert client.post(LINK_URL, format="json").status_code == 403

    def test_staff_without_the_ability_are_refused(self, client, acting_as):
        acting_as([abilities.SEARCH_READ], user=UserFactory(is_staff=True))

        assert client.post(LINK_URL, format="json").status_code == 403

    def test_anonymous_callers_are_refused(self, client):
        assert client.post(LINK_URL, format="json").status_code == 401


class TestDownload:
    def mint(self, client, acting_as) -> str:
        acting_as([abilities.BLOG_WRITE], user=UserFactory(is_staff=True))
        return client.post(LINK_URL, format="json").json()["url"]

    def follow(self, client, url):
        # The browser follows the link with no bearer token: the signature is the credential.
        client.credentials()
        parts = urlsplit(url)
        return client.get(f"{parts.path}?{parts.query}")

    def test_the_link_downloads_an_installable_zip(self, client, acting_as):
        response = self.follow(client, self.mint(client, acting_as))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        assert response["Content-Disposition"] == 'attachment; filename="cars-images-publisher-1.0.0.zip"'
        names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
        assert "cars-images-publisher/cars-images-publisher.php" in names

    def test_a_link_works_once(self, client, acting_as):
        url = self.mint(client, acting_as)
        self.follow(client, url)

        assert self.follow(client, url).status_code == 410

    def test_a_tampered_link_is_refused(self, client, acting_as):
        url = self.mint(client, acting_as)

        assert self.follow(client, url[:-3] + "xyz").status_code == 403

    def test_an_expired_link_is_refused(self, client, acting_as, time_machine, settings):
        time_machine.move_to("2026-09-16T10:00:00Z", tick=False)
        url = self.mint(client, acting_as)
        time_machine.move_to("2026-09-16T11:00:00Z", tick=False)

        assert self.follow(client, url).status_code == 403

    def test_a_request_without_a_token_is_refused(self, client):
        assert client.get("/downloads/wordpress-plugin").status_code == 403
