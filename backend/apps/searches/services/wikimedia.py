"""Wikimedia Commons API client. Port of app/Services/Images/WikimediaClient.php."""

import hashlib
import re
import time
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache

BLOCK_STATUSES = frozenset({429, 403, 503})
# Hard ceiling on requests for one category, so an endless continuation cannot spin a request forever.
MAX_CATEGORY_REQUESTS = 10
# {{category redirect}} hops to follow, so a redirect cycle cannot stall a request.
MAX_CATEGORY_REDIRECTS = 2
RESPONSE_EXCERPT_CHARS = 1024

_CATEGORY_PREFIX = re.compile(r"^Category:", re.IGNORECASE)
_CATEGORY_REDIRECT = re.compile(r"\{\{\s*category redirect\s*\|\s*([^}|]+?)\s*\}\}", re.IGNORECASE)


class WikimediaBlockedError(Exception):
    """Raised on HTTP 429/403/503. Never retried."""

    def __init__(self, status: int, retry_after_seconds: int | None = None, response_excerpt: str = ""):
        retry_after = "n/a" if retry_after_seconds is None else retry_after_seconds
        super().__init__(f"Wikimedia returned HTTP {status} (Retry-After: {retry_after})")
        self.status = status
        self.retry_after_seconds = retry_after_seconds
        self.response_excerpt = response_excerpt


class WikimediaClient:
    def resolve_category(self, name: str, depth: int = 0) -> str | None:
        """The canonical name of a populated category, following {{category redirect}}; None if unusable.

        A block or network failure raises rather than returning None, so it is never cached as a miss.
        """
        response = self._request(
            {
                "titles": f"Category:{name}",
                "prop": "categoryinfo|revisions",
                "rvprop": "content",
                "rvslots": "main",
                "redirects": 1,
            }
        )

        page = _first(_dig(response, "query", "pages"))
        # An unrepresentable title comes back as {"invalid": true} with no "missing" key.
        if not isinstance(page, dict) or page.get("missing") or page.get("invalid"):
            return None

        resolved = _CATEGORY_PREFIX.sub("", str(page.get("title") or name), count=1)

        # Commons redirects categories with a template, which the API reports as an ordinary empty page.
        content = _dig(_first(page.get("revisions")), "slots", "main", "content")
        if depth < MAX_CATEGORY_REDIRECTS and (match := _CATEGORY_REDIRECT.search(str(content or ""))):
            return self.resolve_category(_CATEGORY_PREFIX.sub("", match.group(1).strip(), count=1), depth + 1)

        # Subcategories count: deepcategory: searches read through them.
        info = page.get("categoryinfo")
        info = info if isinstance(info, dict) else {}
        return resolved if int(info.get("files") or 0) + int(info.get("subcats") or 0) > 0 else None

    def files_in_category(self, category: str, year: int) -> list[dict]:
        """Mapped image dicts: provider, provider_image_id, title, description, source_url,
        thumbnail_url, width, height, mime, license, attribution, metadata."""
        key = self._cache_key(category, year)
        files = cache.get(key)
        if files is None:
            files = self._fetch_category_files(category, year)
            cache.set(key, files, settings.WIKIMEDIA["cache_ttl"])
        return files

    def forget_category(self, category: str, year: int) -> None:
        cache.delete(self._cache_key(category, year))

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """One Commons API call with the shared retry policy, block detection and etiquette headers."""
        config = settings.WIKIMEDIA
        query = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "origin": "*",
            "maxlag": config["maxlag"],
            **params,
        }
        attempts = max(1, int(config["retry_times"]))
        attempt = 0

        while True:
            attempt += 1
            try:
                response = httpx.get(
                    config["base_url"],
                    params=query,
                    headers={"User-Agent": config["user_agent"]},
                    timeout=config["timeout"],
                    follow_redirects=True,
                )
            except httpx.TransportError:
                if attempt == attempts:
                    raise
            else:
                if response.status_code in BLOCK_STATUSES:
                    raise _blocked_error(response)
                if response.is_success:
                    return _json_object(response)
                if attempt == attempts:
                    response.raise_for_status()

            time.sleep(config["retry_sleep_ms"] * 2 ** (attempt - 1) / 1000)

    def _cache_key(self, category: str, year: int) -> str:
        """The file cap is part of the key: an answer built under a smaller cap is a different answer."""
        raw = f"{category}|{settings.WIKIMEDIA['category_max_files']}|{year}"
        return "wikimedia_category_" + hashlib.md5(raw.encode()).hexdigest()

    def _fetch_category_files(self, category: str, year: int) -> list[dict]:
        max_files = int(settings.WIKIMEDIA["category_max_files"])
        page_size = int(settings.WIKIMEDIA["category_page_size"])

        files: list[dict] = []
        seen: set[str] = set()
        continuation: dict[str, Any] = {}
        requests = 0

        while True:
            # MediaWiki continuation: echo the entire `continue` object back, not one cherry-picked key.
            response = self._request(
                {
                    "prop": "imageinfo",
                    "generator": "search",
                    "gsrsearch": f'deepcategory:"{category}" intitle:{year}',
                    "gsrnamespace": 6,
                    "gsrlimit": page_size,
                    "iiprop": "url|size|mime|extmetadata",
                    "iiurlwidth": 1200,
                    **continuation,
                }
            )

            for page in _dig(response, "query", "pages") or []:
                if not isinstance(page, dict):
                    continue
                image = _map_page(page)
                # Namespace 6 also holds PDFs and DjVu; iicontinue re-lists pages, so dedupe by page id.
                is_image = image["source_url"] is not None and str(image["mime"] or "").startswith("image/")
                if is_image and image["provider_image_id"] not in seen:
                    seen.add(image["provider_image_id"])
                    files.append(image)

            continuation = response.get("continue")
            continuation = continuation if isinstance(continuation, dict) else {}
            requests += 1
            if not continuation or len(files) >= max_files or requests >= MAX_CATEGORY_REQUESTS:
                break

        return files[:max_files]


def _map_page(page: dict) -> dict:
    image_info = _first(page.get("imageinfo"))
    image_info = image_info if isinstance(image_info, dict) else None
    pageid = page.get("pageid")
    image = {
        "provider": "wikimedia",
        "provider_image_id": "" if pageid is None else str(pageid),
        "title": page["title"] if page.get("title") is not None else "",
        "description": None,
        "source_url": None,
        "thumbnail_url": None,
        "width": None,
        "height": None,
        "mime": None,
        "license": None,
        "attribution": None,
        "metadata": page,
    }
    if image_info is None:
        return image

    ext = image_info.get("extmetadata")
    ext = ext if isinstance(ext, dict) else {}
    attribution = [part for part in (_ext_value(ext, key) for key in ("Artist", "Credit", "UsageTerms")) if part]
    url = image_info.get("url")

    return {
        **image,
        "description": _ext_value(ext, "ImageDescription"),
        "source_url": url,
        "thumbnail_url": image_info["thumburl"] if image_info.get("thumburl") is not None else url,
        "width": image_info.get("width"),
        "height": image_info.get("height"),
        "mime": image_info.get("mime"),
        "license": _ext_value(ext, "LicenseShortName"),
        "attribution": " | ".join(attribution) if attribution else None,
    }


def _ext_value(ext: dict, key: str) -> str | None:
    entry = ext.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    return str(entry["value"]).strip() or None


def _blocked_error(response: httpx.Response) -> WikimediaBlockedError:
    retry_after = response.headers.get("Retry-After", "").strip()
    return WikimediaBlockedError(
        status=response.status_code,
        retry_after_seconds=int(retry_after) if re.fullmatch(r"[0-9]+", retry_after) else None,
        response_excerpt=response.text[:RESPONSE_EXCERPT_CHARS],
    )


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else None


def _dig(value: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
