"""Commons and WordPress are both faked: nothing here downloads or uploads for real."""

from email.parser import BytesParser
from email.policy import default as email_policy

import httpx
import pytest
import respx

from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.publishing.models import BlogPostMedia
from apps.publishing.services import media, wordpress
from tests.exports.images import dimensions, encode_image
from tests.factories import BlogPostFactory, CarImageFactory, CarSearchFactory

pytestmark = pytest.mark.django_db

WP_MEDIA = "https://wp.test/wp-json/wp/v2/media"
APPROVED = CarImage.ReviewStatus.APPROVED
JPEG = encode_image(64, 48)


@pytest.fixture
def http():
    """Intercepts Commons downloads and WordPress uploads alike."""
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def wp_media(http):
    """A WordPress media endpoint that hands out ids 1, 2, 3, ..."""
    counter = {"next": 1}

    def created(request):
        media_id = counter["next"]
        counter["next"] += 1
        body = {"id": media_id, "source_url": f"https://wp.test/uploads/{media_id}.jpg", "media_details": {}}
        return httpx.Response(201, json=body)

    return http.post(WP_MEDIA).mock(side_effect=created)


@pytest.fixture
def post():
    return BlogPostFactory(make="Toyota", model="RAV4", year=1997, slug="1997-toyota-rav4")


def approved(http, n, *, body=JPEG, status=200, **fields):
    url = f"https://upload.wikimedia.org/commons/{n}.jpg"
    http.get(url).mock(return_value=httpx.Response(status, content=body))
    defaults = {"make": "Toyota", "model": "RAV4", "year": 1997, "review_status": APPROVED, "source_url": url}
    return CarImageFactory(**{**defaults, **fields})


def run_sync(post):
    with wordpress.client() as wp, media.fetch_client() as fetcher:
        return media.sync(post, wp=wp, fetcher=fetcher)


def uploaded_parts(request) -> dict:
    raw = f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode() + request.content
    message = BytesParser(policy=email_policy).parsebytes(raw)
    return {
        part.get_param("name", header="content-disposition"): (part.get_filename(), part.get_payload(decode=True))
        for part in message.iter_parts()
    }


class TestWhichImages:
    def test_only_approved_images_of_the_same_vehicle_are_uploaded(self, http, wp_media, post):
        approved(http, 1)
        approved(http, 2)
        approved(http, 3, review_status=CarImage.ReviewStatus.PENDING)
        approved(http, 4, review_status=CarImage.ReviewStatus.REJECTED)
        approved(http, 5, year=1998)
        approved(http, 6, make="Honda", model="CR-V")

        result = run_sync(post)

        assert (result.uploaded, wp_media.call_count) == (2, 2)

    def test_make_and_model_match_whatever_their_case(self, http, wp_media, post):
        approved(http, 1, make="toyota", model="rav4")

        assert run_sync(post).uploaded == 1

    def test_a_vehicle_with_no_model_uses_only_images_with_no_model(self, http, wp_media):
        post = BlogPostFactory(make="Toyota", model=None, year=1997, slug="1997-toyota")
        approved(http, 1, model=None, car_search=None)
        approved(http, 2)

        assert run_sync(post).uploaded == 1

    def test_the_same_commons_file_found_by_two_searches_is_uploaded_once(self, http, wp_media, post):
        approved(http, 1, provider_image_id="page-77", car_search=CarSearchFactory())
        approved(http, 2, provider_image_id="page-77", car_search=CarSearchFactory())

        assert run_sync(post).uploaded == 1

    def test_the_per_post_image_cap_is_respected(self, http, wp_media, post, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_images_per_post": 2}
        for n in range(3):
            approved(http, n)

        assert run_sync(post).uploaded == 2

    def test_an_image_that_fails_does_not_use_up_a_place_under_the_cap(self, http, wp_media, post, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_images_per_post": 2}
        approved(http, 1, status=404)
        approved(http, 2)
        approved(http, 3)

        assert run_sync(post).uploaded == 2


class TestOrdering:
    def test_the_first_approved_image_is_featured_and_positions_follow_approval_order(self, http, wp_media, post):
        first, second = approved(http, 1), approved(http, 2)

        run_sync(post)

        stored = list(post.media.order_by("position"))
        assert [(item.car_image, item.is_featured) for item in stored] == [(first, True), (second, False)]

    def test_when_the_first_image_fails_the_next_one_is_featured(self, http, wp_media, post):
        approved(http, 1, status=404)
        second = approved(http, 2)

        run_sync(post)

        assert BlogPostMedia.objects.get(is_featured=True).car_image == second


class TestRerun:
    def test_a_rerun_uploads_nothing_already_on_wordpress(self, http, wp_media, post):
        approved(http, 1)
        approved(http, 2)

        run_sync(post)
        again = run_sync(post)

        assert (wp_media.call_count, again.uploaded, again.already_uploaded) == (2, 0, 2)
        assert post.media.count() == 2


class TestUpload:
    def test_images_are_resized_before_upload(self, http, wp_media, post, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "image_max_width": 800}
        approved(http, 1, body=encode_image(3000, 2000))

        run_sync(post)

        _, data = uploaded_parts(wp_media.calls.last.request)["file"]
        assert dimensions(data) == (800, 533)

    def test_uploads_get_readable_seo_filenames(self, http, wp_media, post):
        approved(http, 1)
        approved(http, 2)

        run_sync(post)

        names = [uploaded_parts(call.request)["file"][0] for call in wp_media.calls]
        assert names == ["1997-toyota-rav4.jpg", "1997-toyota-rav4-2.jpg"]

    def test_alt_text_title_and_credit_come_from_commons(self, http, wp_media, post):
        approved(
            http,
            1,
            title="File:1997_Toyota_RAV4_front (2).jpg",
            license="CC BY-SA 4.0",
            attribution="Jane Photographer",
            metadata={"imageinfo": [{"descriptionurl": "https://commons.wikimedia.org/wiki/File:Front.jpg"}]},
        )

        run_sync(post)

        parts = uploaded_parts(wp_media.calls.last.request)
        stored = post.media.get()
        assert parts["alt_text"][1].decode() == "1997 Toyota RAV4 front"
        assert parts["caption"][1].decode() == "1997 Toyota RAV4 front — CC BY-SA 4.0 — Jane Photographer"
        assert stored.credit_url == "https://commons.wikimedia.org/wiki/File:Front.jpg"
        assert (stored.wp_media_id, stored.wp_source_url) == (1, "https://wp.test/uploads/1.jpg")

    def test_alt_text_names_the_vehicle_when_the_commons_title_does_not(self, http, wp_media, post):
        approved(http, 1, title="File:RAV4 interior.jpg")

        run_sync(post)

        assert post.media.get().alt_text == "1997 Toyota RAV4 — RAV4 interior"

    def test_without_a_description_url_the_credit_links_the_commons_file_page(self, http, wp_media, post):
        approved(http, 1, title="File:1997 Toyota RAV4 front (2).jpg", metadata=None)

        run_sync(post)

        assert post.media.get().credit_url == "https://commons.wikimedia.org/wiki/File:1997_Toyota_RAV4_front_(2).jpg"

    def test_commons_is_asked_with_a_descriptive_user_agent(self, http, wp_media, post, settings):
        image = approved(http, 1)

        run_sync(post)

        fetch = next(call for call in http.calls if str(call.request.url) == image.source_url)
        assert fetch.request.headers["User-Agent"] == settings.WIKIMEDIA["user_agent"]


class TestFailures:
    def test_a_failed_download_is_logged_and_skipped_without_stopping_the_rest(self, http, wp_media, post):
        broken = approved(http, 1, status=404)
        approved(http, 2)

        result = run_sync(post)

        assert (result.uploaded, result.failed) == (1, 1)
        event = ErrorEvent.objects.get()
        assert (event.context, event.car_image, event.blog_post) == (ErrorEvent.Context.IMAGE_DOWNLOAD, broken, post)

    def test_an_oversized_original_is_skipped_before_it_is_decoded(self, http, wp_media, post, settings):
        """Decoding a huge Commons original is the memory ceiling on a 512 MB instance."""
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "image_max_bytes": 1000}
        approved(http, 1, body=b"\xff" * 5000)

        result = run_sync(post)

        assert (result.uploaded, wp_media.call_count) == (0, 0)
        assert "larger than" in ErrorEvent.objects.get().message

    def test_an_oversized_original_sent_without_a_length_is_abandoned_mid_download(
        self, http, wp_media, post, settings
    ):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "image_max_bytes": 1000}
        image = approved(http, 1)
        # A generator body is streamed without a Content-Length header.
        http.get(image.source_url).mock(return_value=httpx.Response(200, content=(b"\xff" * 600 for _ in range(10))))

        result = run_sync(post)

        assert (result.uploaded, wp_media.call_count) == (0, 0)
        assert "larger than" in ErrorEvent.objects.get().message

    def test_rejected_credentials_stop_the_sync(self, http, post):
        http.post(WP_MEDIA).mock(return_value=httpx.Response(401, json={"code": "rest_cannot_create"}))
        approved(http, 1)
        approved(http, 2)

        with pytest.raises(wordpress.WordPressBlockedError):
            run_sync(post)

        assert http.routes[0].call_count == 1

    def test_an_upload_that_may_have_succeeded_is_logged_and_skipped(self, http, post):
        http.post(WP_MEDIA).mock(
            side_effect=[
                httpx.Response(502),
                httpx.Response(201, json={"id": 9, "source_url": "https://wp.test/uploads/9.jpg"}),
            ]
        )
        approved(http, 1)
        approved(http, 2)

        result = run_sync(post)

        event = ErrorEvent.objects.get()
        assert (result.uploaded, result.failed) == (1, 1)
        assert (event.context, event.details["may_have_succeeded"]) == (ErrorEvent.Context.WORDPRESS_MEDIA, True)
