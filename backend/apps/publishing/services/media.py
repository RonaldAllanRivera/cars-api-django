"""
Puts a post's approved images on WordPress: fetch from Commons, resize, upload.

Images are fetched and resized here because Wikimedia's thumbnail CDN rejects
datacenter IPs, the same reason the ZIP export does it. One image is in memory
at a time, and an original larger than PUBLISH_IMAGE_MAX_BYTES is abandoned
while downloading, before Pillow ever decodes it.

A BlogPostMedia row is written only after WordPress accepts an upload, so a
resumed run uploads just what is missing. A failed image is logged and skipped;
only rejected credentials or rate limiting stop the run.
"""

import mimetypes
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from django.conf import settings
from django.db.models import Q
from django.utils.text import slugify

from apps.exports.services.filenames import build_ranked, extension_from_url
from apps.exports.services.resizer import resize_image
from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.publishing.models import BlogPost, BlogPostMedia
from apps.publishing.services.titles import clean_title
from apps.publishing.services.wordpress import WordPressBlockedError, WordPressClient, WordPressError

COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/"


@dataclass
class MediaSync:
    uploaded: int = 0
    already_uploaded: int = 0
    failed: int = 0


@contextmanager
def fetch_client() -> Iterator[httpx.Client]:
    """One connection to Commons for a run; upload.wikimedia.org rejects requests without a descriptive agent."""
    headers = {"User-Agent": settings.WIKIMEDIA["user_agent"]}
    timeout = settings.CARS_PUBLISHING["image_fetch_timeout"]
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        yield client


def approved_images(post: BlogPost) -> list[CarImage]:
    """The vehicle's approved images, oldest approval first, one per Commons file."""
    images = CarImage.objects.filter(
        review_status=CarImage.ReviewStatus.APPROVED, year=post.year, make__iexact=post.make
    )
    if post.model:
        images = images.filter(model__iexact=post.model)
    else:
        images = images.filter(Q(model__isnull=True) | Q(model=""))

    seen: set[tuple[str, str]] = set()
    unique = []
    for image in images.order_by("id"):
        # Two searches can find the same Commons file; it is one photo, uploaded once.
        key = (image.provider, image.provider_image_id or image.source_url)
        if key not in seen:
            seen.add(key)
            unique.append(image)
    return unique


def sync(post: BlogPost, *, wp: WordPressClient, fetcher: httpx.Client) -> MediaSync:
    """Upload what is missing, up to the per-post cap, then mark the first image featured."""
    limit = settings.CARS_PUBLISHING["max_images_per_post"]
    stored = set(post.media.values_list("car_image_id", flat=True))
    result = MediaSync()

    for position, image in enumerate(approved_images(post)):
        # A failed image does not take a place under the cap; the next approved one is tried.
        if result.uploaded + result.already_uploaded >= limit:
            break
        if image.pk in stored:
            result.already_uploaded += 1
        elif _upload(post, image, position, wp=wp, fetcher=fetcher):
            result.uploaded += 1
        else:
            result.failed += 1

    _mark_featured(post)
    return result


def _upload(post: BlogPost, image: CarImage, position: int, *, wp: WordPressClient, fetcher: httpx.Client) -> bool:
    config = settings.CARS_PUBLISHING
    original = _fetch(post, image, fetcher, config["image_max_bytes"])
    if original is None:
        return False
    data, extension = resize_image(
        original, config["image_max_width"], extension_from_url(image.source_url), config["image_jpeg_quality"]
    )
    del original

    vehicle = str(post)
    title = clean_title(image.title) or vehicle
    alt_text = title if vehicle.casefold() in title.casefold() else f"{vehicle} — {title}"
    caption = " — ".join(part for part in (title, image.license, image.attribution) if part)
    filename = _filename(post, extension, position)
    try:
        uploaded = wp.upload_media(
            data=data, filename=filename, mime=_mime(extension), title=title, alt_text=alt_text, caption=caption
        )
    except WordPressBlockedError:
        raise
    except WordPressError as error:
        error_logger.record(
            ErrorEvent.Context.WORDPRESS_MEDIA,
            error,
            blog_post=post,
            car_image=image,
            car_search=image.car_search_id,
            details={
                "http_status": error.status,
                "code": error.code,
                "filename": filename,
                "may_have_succeeded": error.may_have_succeeded,
                "response_excerpt": error.response_excerpt,
            },
        )
        return False

    details = uploaded.get("media_details") or {}
    BlogPostMedia.objects.create(
        blog_post=post,
        car_image=image,
        wp_media_id=uploaded["id"],
        wp_source_url=uploaded.get("source_url") or "",
        filename=filename,
        alt_text=alt_text,
        caption=caption,
        credit_url=_credit_url(image),
        width=details.get("width"),
        height=details.get("height"),
        bytes_uploaded=len(data),
        position=position,
    )
    return True


def _fetch(post: BlogPost, image: CarImage, fetcher: httpx.Client, max_bytes: int) -> bytes | None:
    """The original's bytes, or None after logging why; stops reading once it passes max_bytes."""
    try:
        with fetcher.stream("GET", image.source_url) as response:
            if not response.is_success:
                return _fetch_failed(post, image, f"Image download failed with HTTP {response.status_code}")
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                return _fetch_failed(post, image, f"Image is larger than {max_bytes} bytes ({declared})")
            buffer = bytearray()
            for chunk in response.iter_bytes():
                buffer.extend(chunk)
                if len(buffer) > max_bytes:
                    return _fetch_failed(post, image, f"Image is larger than {max_bytes} bytes")
            return bytes(buffer)
    except httpx.HTTPError as error:
        return _fetch_failed(post, image, f"Image download failed: {error}")


def _fetch_failed(post: BlogPost, image: CarImage, message: str) -> None:
    error_logger.record(
        ErrorEvent.Context.IMAGE_DOWNLOAD,
        message,
        blog_post=post,
        car_image=image,
        car_search=image.car_search_id,
        details={"url": image.source_url},
    )
    return None


def _mark_featured(post: BlogPost) -> None:
    """The lowest position that made it to WordPress is featured, so a failed first image never leaves a gap."""
    first = post.media.order_by("position", "id").values_list("pk", flat=True).first()
    if first is None:
        return
    post.media.exclude(pk=first).update(is_featured=False)
    post.media.filter(pk=first).update(is_featured=True)


def _filename(post: BlogPost, extension: str, position: int) -> str:
    """ "1997-toyota-rav4.jpg", then "1997-toyota-rav4-2.jpg": readable in the media library and to search engines."""
    base, _, ext = build_ranked(post.year, post.make, post.model, extension, position + 1).rpartition(".")
    return f"{slugify(base)}.{ext}"


def _mime(extension: str) -> str:
    return mimetypes.guess_type(f"image.{extension}")[0] or "application/octet-stream"


def _credit_url(image: CarImage) -> str:
    """The Commons file page, where the licence and author are published."""
    info = ((image.metadata or {}).get("imageinfo") or [{}])[0]
    url = info.get("descriptionurl") if isinstance(info, dict) else None
    if isinstance(url, str) and url.startswith("https://"):
        return url
    if image.title and image.title.startswith("File:"):
        return COMMONS_FILE_PAGE + quote(image.title.replace(" ", "_"), safe=":()_,.-")
    return ""
