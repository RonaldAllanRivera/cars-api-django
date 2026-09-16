"""Every test runs against a fake WordPress: nothing here reaches a real site."""

import base64
import json
import re

import httpx
import pytest
from django.views.debug import ExceptionReporter

from apps.publishing.services import wordpress

POST = {"id": 42, "link": "https://wp.test/?p=42", "status": "draft", "slug": "1997-toyota-rav4"}
MEDIA = {"id": 7, "source_url": "https://wp.test/wp-content/uploads/1997-toyota-rav4.jpg", "media_details": {}}


def wp_error(status, code="rest_error", message="Something went wrong.", headers=None):
    return httpx.Response(status, json={"code": code, "message": message, "data": {"status": status}}, headers=headers)


class TestConfiguration:
    def test_requests_authenticate_with_the_application_password(self, wp_site):
        route = wp_site.get("/posts").mock(return_value=httpx.Response(200, json=[]))

        with wordpress.client() as client:
            client.find_post_by_slug("1997-toyota-rav4")

        expected = base64.b64encode(b"publisher:abcdabcdabcdabcdabcdabcd").decode()
        assert route.calls.last.request.headers["Authorization"] == f"Basic {expected}"

    def test_a_missing_setting_fails_before_any_request(self, wp_site, settings):
        settings.WORDPRESS = {**settings.WORDPRESS, "app_password": ""}
        route = wp_site.route().mock(return_value=httpx.Response(200, json=[]))

        with pytest.raises(wordpress.WordPressError, match="WORDPRESS_APP_PASSWORD"), wordpress.client():
            pass

        assert route.call_count == 0

    def test_django_error_reports_never_show_the_application_password(self, monkeypatch):
        """Fails while the client is built, the frame whose locals hold the password."""

        def broken_client(**options):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(wordpress.httpx, "Client", broken_client)

        with pytest.raises(RuntimeError) as raised, wordpress.client():
            pass

        frames = ExceptionReporter(None, raised.type, raised.value, raised.tb).get_traceback_frames()
        client_frames = [frame for frame in frames if frame["filename"].endswith("wordpress.py")]
        assert client_frames
        assert "abcdabcdabcdabcdabcdabcd" not in repr([frame["vars"] for frame in client_frames])


class TestMedia:
    def test_an_image_is_uploaded_with_its_alt_text_and_credit_in_one_request(self, wp_site):
        route = wp_site.post("/media").mock(return_value=httpx.Response(201, json=MEDIA))

        with wordpress.client() as client:
            media = client.upload_media(
                data=b"\xff\xd8jpeg-bytes",
                filename="1997-toyota-rav4.jpg",
                mime="image/jpeg",
                title="1997 Toyota RAV4",
                alt_text="1997 Toyota RAV4 front view",
                caption="1997 Toyota RAV4 front — CC BY-SA 4.0 — Jane Photographer",
            )

        body = route.calls.last.request.content
        assert media["id"] == 7
        assert b'filename="1997-toyota-rav4.jpg"' in body
        assert b"Content-Type: image/jpeg" in body
        assert b"\xff\xd8jpeg-bytes" in body
        assert b"1997 Toyota RAV4 front view" in body
        assert "1997 Toyota RAV4 front — CC BY-SA 4.0 — Jane Photographer".encode() in body


class TestPosts:
    def test_a_post_is_created_as_json(self, wp_site):
        route = wp_site.post("/posts").mock(return_value=httpx.Response(201, json=POST))

        with wordpress.client() as client:
            created = client.create_post({"title": "1997 Toyota RAV4", "status": "draft"})

        assert created["id"] == 42
        assert json.loads(route.calls.last.request.content) == {"title": "1997 Toyota RAV4", "status": "draft"}

    def test_an_existing_post_is_updated_in_place(self, wp_site):
        route = wp_site.post("/posts/42").mock(return_value=httpx.Response(200, json=POST))

        with wordpress.client() as client:
            client.update_post(42, {"title": "New title"})

        assert route.call_count == 1

    def test_updating_a_post_deleted_in_wordpress_raises_not_found(self, wp_site):
        wp_site.post("/posts/42").mock(return_value=wp_error(404, "rest_post_invalid_id", "Invalid post ID."))

        with pytest.raises(wordpress.WordPressNotFoundError), wordpress.client() as client:
            client.update_post(42, {"title": "New title"})

    def test_a_draft_is_found_by_slug_across_unpublished_statuses(self, wp_site):
        route = wp_site.get("/posts").mock(return_value=httpx.Response(200, json=[POST]))

        with wordpress.client() as client:
            found = client.find_post_by_slug("1997-toyota-rav4")

        params = route.calls.last.request.url.params
        assert found["id"] == 42
        assert (params["slug"], params["context"]) == ("1997-toyota-rav4", "edit")
        assert set(params["status"].split(",")) >= {"draft", "pending", "future", "publish", "private"}

    def test_no_match_by_slug_is_none(self, wp_site):
        wp_site.get("/posts").mock(return_value=httpx.Response(200, json=[]))

        with wordpress.client() as client:
            assert client.find_post_by_slug("nothing-here") is None


class TestErrors:
    def test_the_wordpress_error_code_and_message_are_surfaced(self, wp_site):
        wp_site.post("/posts").mock(return_value=wp_error(400, "rest_invalid_param", "Invalid parameter(s): meta"))

        with pytest.raises(wordpress.WordPressError) as failure, wordpress.client() as client:
            client.create_post({})

        error = failure.value
        assert (error.status, error.code) == (400, "rest_invalid_param")
        assert "Invalid parameter(s): meta" in str(error)
        assert "rest_invalid_param" in error.response_excerpt

    @pytest.mark.parametrize("status", [401, 403])
    def test_rejected_credentials_stop_the_run(self, wp_site, status):
        wp_site.post("/posts").mock(return_value=wp_error(status, "rest_cannot_create"))

        with pytest.raises(wordpress.WordPressBlockedError), wordpress.client() as client:
            client.create_post({})

    def test_a_rate_limit_stops_with_the_wait_the_site_asked_for(self, wp_site):
        wp_site.post("/posts").mock(return_value=wp_error(429, headers={"Retry-After": "30"}))

        with pytest.raises(wordpress.WordPressBlockedError) as blocked, wordpress.client() as client:
            client.create_post({})

        assert blocked.value.retry_after_seconds == 30

    def test_a_redirect_is_refused_rather_than_turning_the_post_into_a_get(self, wp_site):
        """httpx re-sends a redirected POST as a GET: "create a post" would become "list posts"."""
        route = wp_site.post("/posts").mock(
            return_value=httpx.Response(301, headers={"Location": "https://www.wp.test/wp-json/wp/v2/posts"})
        )

        with pytest.raises(wordpress.WordPressError, match=re.escape("www.wp.test")), wordpress.client() as client:
            client.create_post({})

        assert route.call_count == 1


class TestRetries:
    def test_a_read_is_retried_after_a_server_error(self, wp_site):
        route = wp_site.get("/posts").mock(side_effect=[wp_error(502), httpx.Response(200, json=[])])

        with wordpress.client() as client:
            client.find_post_by_slug("x")

        assert route.call_count == 2

    def test_a_write_is_retried_when_the_connection_was_refused(self, wp_site):
        route = wp_site.post("/posts").mock(side_effect=[httpx.ConnectError("refused"), httpx.Response(201, json=POST)])

        with wordpress.client() as client:
            client.create_post({})

        assert route.call_count == 2

    def test_a_write_that_may_have_succeeded_is_not_retried(self, wp_site):
        """A 502 or a timeout after sending can hide a created post; a retry would create a second one."""
        route = wp_site.post("/posts").mock(return_value=wp_error(502))

        with pytest.raises(wordpress.WordPressError) as failure, wordpress.client() as client:
            client.create_post({})

        assert route.call_count == 1
        assert failure.value.may_have_succeeded is True

    def test_a_timed_out_write_is_not_retried(self, wp_site):
        route = wp_site.post("/media").mock(side_effect=httpx.ReadTimeout("slow"))

        with pytest.raises(wordpress.WordPressError) as failure, wordpress.client() as client:
            client.upload_media(data=b"x", filename="a.jpg", mime="image/jpeg", title="", alt_text="", caption="")

        assert route.call_count == 1
        assert failure.value.may_have_succeeded is True
