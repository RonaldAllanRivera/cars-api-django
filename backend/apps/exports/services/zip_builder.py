"""
Builds the downloadable ZIP for an approved batch.

Originals are fetched from Wikimedia's upload host and resized locally: the
thumbnail CDN rejects requests from datacenter IPs.
"""

import zipfile
from collections.abc import Iterable

import httpx
from django.conf import settings

from apps.exports.services.filenames import BaseNameSequence, extension_from_url
from apps.exports.services.resizer import resize_image
from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger

FETCH_TIMEOUT_SECONDS = 30


def build_zip_to_file(images: Iterable[CarImage], path: str) -> int:
    """Returns the number of images added; 0 means nothing was written."""
    max_width = settings.CARS_IMAGES["download_max_width"]
    quality = settings.CARS_IMAGES["download_jpeg_quality"]
    names = BaseNameSequence()
    archive: zipfile.ZipFile | None = None
    added = 0

    # upload.wikimedia.org rejects requests without a descriptive User-Agent.
    headers = {"User-Agent": settings.WIKIMEDIA["user_agent"]}
    try:
        with httpx.Client(headers=headers, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for image in images:
                body = _fetch(client, image)
                if body is None:
                    continue
                data, extension = resize_image(body, max_width, extension_from_url(image.source_url), quality)
                # Named only after a successful fetch, so skips leave no gaps in the numbering.
                filename = names.next(image.year, image.make, image.model, extension)
                if archive is None:
                    archive = zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED)
                archive.writestr(filename, data)
                added += 1
    finally:
        if archive is not None:
            archive.close()
    return added


def _fetch(client: httpx.Client, image: CarImage) -> bytes | None:
    """The image's bytes, or None after recording why they could not be fetched."""
    url = image.source_url
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        _record_failure(image, exc, message=f"Image fetch failed: {exc}", http_status=None, excerpt=None)
        return None

    if not response.is_success:
        excerpt = response.content[: error_logger.DETAIL_STRING_BYTES].decode("utf-8", errors="replace")
        _record_failure(
            image,
            f"Image fetch failed with HTTP {response.status_code}",
            http_status=response.status_code,
            excerpt=excerpt,
        )
        return None
    return response.content


def _record_failure(
    image: CarImage,
    error: BaseException | str,
    *,
    http_status: int | None,
    excerpt: str | None,
    message: str | None = None,
) -> None:
    error_logger.record(
        ErrorEvent.Context.IMAGE_DOWNLOAD,
        error,
        car_image=image,
        car_search=image.car_search_id,
        message=message,
        details={"http_status": http_status, "url": image.source_url, "response_excerpt": excerpt},
    )
