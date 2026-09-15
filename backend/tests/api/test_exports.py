import csv
import io
import zipfile
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from django.core.cache import cache
from PIL import Image

from apps.accounts import abilities
from apps.images.models import CarImage
from tests.api.helpers import error_fields

pytestmark = pytest.mark.django_db

URL = "/api/v1/exports"


def query_of(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def jpeg_bytes() -> bytes:
    """A real JPEG: the ZIP builder resizes what it fetches."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="JPEG")
    return buffer.getvalue()


def exported_image_ids(response) -> list[int]:
    rows = list(csv.DictReader(io.StringIO(b"".join(response.streaming_content).decode())))
    return [int(row["ImageId"]) for row in rows]


@pytest.fixture
def uploads(respx_mock):
    """The Wikimedia upload host the ZIP builder fetches originals from."""
    return respx_mock.get(url__startswith="https://upload.wikimedia.org/")


@pytest.fixture
def mint(client):
    def request_link(export_format: str, **filters) -> str:
        response = client.post(URL, {"format": export_format, **filters}, format="json")
        assert response.status_code == 201, response.content
        return response.json()["url"]

    return request_link


@pytest.fixture
def browser(client):
    """What follows the link: no bearer token."""

    def follow(url: str):
        client.credentials()
        split = urlsplit(url)
        return client.get(split.path, query_of(url))

    return follow


# --- Minting ---------------------------------------------------------------


def test_it_mints_a_signed_expiring_csv_link(client, acting_as, make_search, make_image, time_machine):
    time_machine.move_to("2026-01-15T09:00:00Z", tick=False)
    user = acting_as()
    make_image(make_search(user))

    response = client.post(URL, {"format": "csv"}, format="json", SERVER_NAME="localhost")

    assert response.status_code == 201
    body = response.json()
    assert list(body) == ["url", "expires_at", "count", "format"]
    assert (body["format"], body["count"]) == ("csv", 1)
    assert body["expires_at"] == "2026-01-15T09:05:00+00:00"
    assert body["url"].startswith("http://localhost/exports/download?format=csv&")
    assert "signature" in query_of(body["url"])


def test_a_zip_link_carries_a_nonce_written_to_the_cache(client, acting_as, make_search, make_image, mint):
    make_image(make_search(acting_as()))

    nonce = query_of(mint("zip"))["nonce"]

    assert cache.get(f"export-nonce:{nonce}") is True


def test_a_csv_link_carries_no_nonce(acting_as, make_search, make_image, mint):
    make_image(make_search(acting_as()))

    assert "nonce" not in query_of(mint("csv"))


def test_it_refuses_an_empty_set(client, acting_as):
    acting_as()

    response = client.post(URL, {"format": "csv"}, format="json")

    assert error_fields(response) == {"format"}
    assert response.json()["errors"]["format"] == ["No images match these filters."]


def test_a_zip_over_the_cap_is_refused_but_a_csv_of_the_same_size_is_not(
    client, acting_as, make_search, make_image, settings
):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "bulk_download_max_images": 1}
    search = make_search(acting_as())
    make_image(search)
    make_image(search)

    response = client.post(URL, {"format": "zip"}, format="json")

    assert error_fields(response) == {"format"}
    assert response.json()["errors"]["format"] == ["2 images match; a ZIP is limited to 1. Narrow the filter."]
    assert client.post(URL, {"format": "csv"}, format="json").status_code == 201


def test_the_filters_travel_through_the_signature(acting_as, make_search, make_image, mint):
    make_image(make_search(acting_as()), review_status="approved")

    assert query_of(mint("csv", review_status="approved"))["review_status"] == "approved"


@pytest.mark.parametrize("body", [{"format": "pdf"}, {}], ids=["unknown", "missing"])
def test_it_rejects_an_unknown_format(client, acting_as, body):
    acting_as()

    assert error_fields(client.post(URL, body, format="json")) == {"format"}


def test_format_and_filter_errors_are_reported_together(client, acting_as):
    acting_as()

    response = client.post(URL, {"format": "pdf", "make_confirmed": "maybe"}, format="json")

    assert error_fields(response) == {"format", "make_confirmed"}


def test_minting_requires_exports_read(client, acting_as, make_search, make_image):
    make_image(make_search(acting_as([abilities.SEARCH_READ])))

    assert client.post(URL, {"format": "csv"}, format="json").status_code == 403


# --- Downloading -----------------------------------------------------------


def test_a_csv_link_downloads_only_the_filtered_rows(acting_as, make_search, make_image, mint, browser):
    search = make_search(acting_as())
    kept = make_image(search, review_status="approved")
    make_image(search, review_status="rejected")

    response = browser(mint("csv", review_status="approved"))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=UTF-8"
    assert response["Content-Disposition"].startswith('attachment; filename="cars-')
    assert exported_image_ids(response) == [kept.id]


def test_the_download_needs_no_bearer_token(client, acting_as, make_search, make_image, mint):
    make_image(make_search(acting_as()))
    url = mint("csv")
    client.credentials()

    assert client.get(url).status_code == 200


@pytest.mark.parametrize("verdict", [False, True])
def test_a_verdict_filter_survives_the_signed_url(acting_as, make_search, make_image, mint, browser, verdict):
    """
    The app sends the verdict as a JSON boolean. If any step between validation
    and the download dropped a `false`, "export the images that did not match"
    would silently become "export everything".
    """
    search = make_search(acting_as())
    wanted = make_image(search, make_confirmed=verdict)
    make_image(search, make_confirmed=not verdict)
    make_image(search, make_confirmed=None)

    assert exported_image_ids(browser(mint("csv", make_confirmed=verdict))) == [wanted.id]


def test_an_import_filter_survives_the_signed_url(acting_as, make_search, make_import, make_image, mint, browser):
    user = acting_as()
    csv_import = make_import(user)
    wanted = make_image(make_search(user, csv_import=csv_import))
    make_image(make_search(user))

    url = mint("csv", csv_import_id=csv_import.id)

    assert query_of(url)["csv_import_id"] == str(csv_import.id)
    assert exported_image_ids(browser(url)) == [wanted.id]


def test_a_tampered_link_is_rejected(acting_as, make_search, make_image, mint, browser):
    make_image(make_search(acting_as()), review_status="approved")
    url = mint("csv", review_status="approved")

    # Widening the filter by editing the URL must fail the signature.
    assert browser(url.replace("review_status=approved", "review_status=rejected")).status_code == 403
    assert browser(url.replace("review_status=approved&", "")).status_code == 403


def test_a_repeated_parameter_is_rejected(client, acting_as, make_search, make_image, mint):
    make_image(make_search(acting_as()), review_status="approved")
    url = mint("csv", review_status="approved")
    client.credentials()

    assert client.get(f"{url}&review_status=rejected").status_code == 403


def test_an_expired_link_is_rejected(acting_as, make_search, make_image, mint, browser, time_machine):
    time_machine.move_to("2026-01-15T09:00:00Z", tick=False)
    make_image(make_search(acting_as()))
    url = mint("csv")

    time_machine.move_to("2026-01-15T09:06:00Z", tick=False)

    assert browser(url).status_code == 403


def test_a_zip_link_works_once_and_is_gone_the_second_time(acting_as, make_search, make_image, mint, browser, uploads):
    uploads.mock(return_value=httpx.Response(200, content=jpeg_bytes(), headers={"Content-Type": "image/jpeg"}))
    make_image(make_search(acting_as()))
    url = mint("zip")

    first = browser(url)
    assert first.status_code == 200
    assert first["Content-Type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(b"".join(first.streaming_content))) as archive:
        assert len(archive.namelist()) == 1
    first.close()

    assert browser(url).status_code == 410


def test_a_zip_marks_its_images_downloaded(acting_as, make_search, make_image, mint, browser, uploads):
    uploads.mock(return_value=httpx.Response(200, content=jpeg_bytes(), headers={"Content-Type": "image/jpeg"}))
    image = make_image(make_search(acting_as()))

    assert browser(mint("zip")).status_code == 200

    image.refresh_from_db()
    assert image.download_status == CarImage.DownloadStatus.DOWNLOADED


def test_the_temporary_zip_is_deleted_once_sent(acting_as, make_search, make_image, mint, browser):
    make_image(make_search(acting_as()))
    written: list[str] = []

    def build(images, path):
        Path(path).write_bytes(b"PK")
        written.append(path)
        return 1

    with mock.patch("api.v1.views.exports.build_zip_to_file", side_effect=build):
        response = browser(mint("zip"))
    assert Path(written[0]).exists()

    b"".join(response.streaming_content)
    response.close()

    assert not Path(written[0]).exists()


def test_a_zip_that_grew_past_the_cap_after_minting_is_refused(
    acting_as, make_search, make_image, mint, browser, settings
):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "bulk_download_max_images": 1}
    search = make_search(acting_as())
    make_image(search)
    url = mint("zip")

    make_image(search)

    assert browser(url).status_code == 422


def test_a_zip_where_every_fetch_failed_is_an_error_not_an_empty_archive(
    acting_as, make_search, make_image, mint, browser, uploads
):
    uploads.mock(return_value=httpx.Response(404, text="gone"))
    image = make_image(make_search(acting_as()))

    assert browser(mint("zip")).status_code == 502
    image.refresh_from_db()
    assert image.download_status == CarImage.DownloadStatus.NOT_DOWNLOADED
