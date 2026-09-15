import os
import zipfile

import httpx
import pytest
import respx

from apps.exports.services.zip_builder import build_zip_to_file
from apps.observability.models import ErrorEvent
from tests.exports.images import dimensions, encode_image
from tests.factories import CarImageFactory, CarSearchFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def zip_path(tmp_path):
    return str(tmp_path / "batch.zip")


@pytest.fixture
def http():
    with respx.mock(assert_all_called=False) as router:
        yield router


def image(url: str, **overrides):
    search = overrides.pop("car_search", None) or CarSearchFactory(make="Toyota", model="RAV4", from_year=1997)
    return CarImageFactory(car_search=search, source_url=url, **overrides)


def test_writes_zip_with_renamed_entries_and_duplicate_suffix(http, zip_path):
    http.get("https://example.com/a.jpg").respond(200, content=b"AAAA")
    http.get("https://example.com/b.png").respond(200, content=b"BBBB")
    search = CarSearchFactory(make="Toyota", model="RAV4", from_year=1997)
    img1 = image("https://example.com/a.jpg", car_search=search)
    img2 = image("https://example.com/b.png", car_search=search)

    added = build_zip_to_file([img1, img2], zip_path)

    assert added == 2
    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == ["1997 Toyota RAV4 2.png", "1997 Toyota RAV4.jpg"]
        assert archive.read("1997 Toyota RAV4.jpg") == b"AAAA"
        assert archive.read("1997 Toyota RAV4 2.png") == b"BBBB"
        assert all(info.compress_type == zipfile.ZIP_DEFLATED for info in archive.infolist())


def test_sends_descriptive_user_agent_when_fetching_images(http, zip_path, settings):
    settings.WIKIMEDIA = {**settings.WIKIMEDIA, "user_agent": "CarsImagesApi/1.0 (ops@example.test)"}
    route = http.get("https://upload.wikimedia.org/a.jpg").respond(200, content=b"AAAA")

    build_zip_to_file([image("https://upload.wikimedia.org/a.jpg")], zip_path)

    assert route.call_count == 1
    assert route.calls.last.request.headers["User-Agent"] == "CarsImagesApi/1.0 (ops@example.test)"


def test_returns_zero_and_writes_nothing_when_all_image_fetches_fail(http, zip_path):
    http.get("https://upload.wikimedia.org/a.jpg").respond(403, text="Forbidden")

    added = build_zip_to_file([image("https://upload.wikimedia.org/a.jpg")], zip_path)

    assert added == 0
    assert not os.path.exists(zip_path)


def test_fetches_the_original_source_url_not_the_thumbnail(http, zip_path):
    thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Foo.jpg/1280px-Foo.jpg"
    original_url = "https://upload.wikimedia.org/wikipedia/commons/4/47/Foo.jpg"
    original = http.get(original_url).respond(200, content=encode_image(2000, 1500))
    thumb = http.get(thumb_url).respond(500, text="boom")

    added = build_zip_to_file([image(original_url, thumbnail_url=thumb_url)], zip_path)

    assert added == 1
    assert original.called
    assert not thumb.called


def test_resizes_large_images_down_in_the_zip(http, zip_path, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "download_max_width": 1600}
    url = "https://upload.wikimedia.org/wikipedia/commons/4/47/Foo.png"
    http.get(url).respond(200, content=encode_image(3000, 2000, fmt="PNG"))
    search = CarSearchFactory(make="Acura", model="NSX", from_year=1999)

    build_zip_to_file([image(url, car_search=search)], zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["1999 Acura NSX.jpg"]
        assert dimensions(archive.read("1999 Acura NSX.jpg"))[0] == 1600


def test_an_image_that_cannot_be_fetched_is_logged_and_the_zip_still_builds(http, zip_path):
    http.get("https://example.com/good.jpg").respond(200, content=encode_image(20, 20))
    http.get("https://example.com/gone.jpg").respond(404, text="Not Found")
    search = CarSearchFactory()
    gone = image("https://example.com/gone.jpg", car_search=search)
    good = image("https://example.com/good.jpg", car_search=search)

    added = build_zip_to_file([gone, good], zip_path)

    assert added == 1
    event = ErrorEvent.objects.get(context=ErrorEvent.Context.IMAGE_DOWNLOAD)
    assert event.message == "Image fetch failed with HTTP 404"
    assert event.car_image_id == gone.pk
    assert event.car_search_id == search.pk
    assert event.details == {
        "http_status": 404,
        "url": "https://example.com/gone.jpg",
        "response_excerpt": "Not Found",
    }
    with zipfile.ZipFile(zip_path) as archive:
        # A skipped image leaves no gap in the duplicate-suffix sequence.
        assert archive.namelist() == ["1997 Toyota RAV4.jpg"]


def test_a_network_error_skips_the_image_instead_of_aborting_the_zip(http, zip_path):
    http.get("https://example.com/timeout.jpg").mock(side_effect=httpx.ConnectTimeout("timed out"))
    http.get("https://example.com/good.jpg").respond(200, content=b"GOOD")
    search = CarSearchFactory()
    broken = image("https://example.com/timeout.jpg", car_search=search)
    good = image("https://example.com/good.jpg", car_search=search)

    added = build_zip_to_file([broken, good], zip_path)

    assert added == 1
    event = ErrorEvent.objects.get(context=ErrorEvent.Context.IMAGE_DOWNLOAD)
    assert event.car_image_id == broken.pk
    assert event.exception_class == "ConnectTimeout"
    assert event.details == {"http_status": None, "url": "https://example.com/timeout.jpg", "response_excerpt": None}


def test_follows_redirects_to_the_image(http, zip_path):
    http.get("https://example.com/old.jpg").respond(301, headers={"Location": "https://example.com/new.jpg"})
    http.get("https://example.com/new.jpg").respond(200, content=b"MOVED")

    added = build_zip_to_file([image("https://example.com/old.jpg")], zip_path)

    assert added == 1
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.read("1997 Toyota RAV4.jpg") == b"MOVED"


def test_a_binary_error_body_is_still_logged(http, zip_path):
    body = encode_image(20, 20, fmt="PNG") * 200
    http.get("https://example.com/error.jpg").respond(503, content=body)

    build_zip_to_file([image("https://example.com/error.jpg")], zip_path)

    excerpt = ErrorEvent.objects.get().details["response_excerpt"]
    assert "PNG" in excerpt
    assert "\x00" not in excerpt
    assert len(excerpt.encode()) <= 1000
