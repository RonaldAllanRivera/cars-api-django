"""
The WordPress REST API client: media uploads and draft posts.

Authenticates with an Application Password over HTTP Basic. Retries follow what
a failure proves, per request method:

- A refused connection proves nothing was sent, so any request is retried.
- A GET is safe to repeat after a server error or a lost response.
- A POST that failed after sending (a 5xx or a timeout) may already have created
  its post or attachment, so it is not retried; the error says so, and the
  publisher recovers by finding the draft by its slug.

Redirects are refused rather than followed: httpx re-sends a redirected POST as
a GET, which would quietly turn "create a post" into "list posts".
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

API_PATH = "/wp-json/wp/v2"
RESPONSE_EXCERPT_CHARS = 1024
# Rejected credentials or rate limiting: every further request would fail the same way.
BLOCK_STATUSES = frozenset({401, 403, 429})
RETRY_STATUSES = frozenset({500, 502, 503, 504})
NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
# A draft the publisher created may since have been scheduled or published by an editor.
FINDABLE_STATUSES = "draft,pending,future,publish,private"
REQUIRED_SETTINGS = {
    "base_url": "WORDPRESS_BASE_URL",
    "username": "WORDPRESS_USERNAME",
    "app_password": "WORDPRESS_APP_PASSWORD",
}


class WordPressError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str = "",
        retry_after_seconds: int | None = None,
        response_excerpt: str = "",
        may_have_succeeded: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        self.response_excerpt = response_excerpt
        self.may_have_succeeded = may_have_succeeded


class WordPressBlockedError(WordPressError):
    """Credentials rejected or rate limited: stop until someone fixes it or the site allows it."""


class WordPressNotFoundError(WordPressError):
    """The post or attachment no longer exists, typically deleted by an editor."""


class WordPressClient:
    def __init__(self, http: httpx.Client, *, retry_times: int, retry_sleep_ms: int):
        self._http = http
        self._attempts = max(1, int(retry_times) + 1)
        self._retry_sleep_ms = retry_sleep_ms

    def find_post_by_slug(self, slug: str) -> dict | None:
        posts = self._request(
            "GET", "/posts", params={"slug": slug, "status": FINDABLE_STATUSES, "context": "edit", "per_page": 1}
        )
        return posts[0] if posts else None

    def create_post(self, payload: dict) -> dict:
        return self._request("POST", "/posts", json=payload)

    def update_post(self, wp_post_id: int, payload: dict) -> dict:
        return self._request("POST", f"/posts/{int(wp_post_id)}", json=payload)

    def upload_media(self, *, data: bytes, filename: str, mime: str, title: str, alt_text: str, caption: str) -> dict:
        """One multipart request carries the file and its alt text and credit."""
        return self._request(
            "POST",
            "/media",
            files={"file": (filename, data, mime)},
            data={"title": title, "alt_text": alt_text, "caption": caption},
        )

    def _request(self, method: str, path: str, **options):
        repeatable = method == "GET"
        for attempt in range(1, self._attempts + 1):
            last = attempt == self._attempts
            try:
                response = self._http.request(method, path, **options)
            except NOT_SENT as error:
                if last:
                    raise WordPressError(f"Could not reach WordPress: {error}") from error
            except httpx.TransportError as error:
                if last or not repeatable:
                    raise WordPressError(
                        f"The response from WordPress was lost after the request was sent: {error}",
                        may_have_succeeded=not repeatable,
                    ) from error
            else:
                if response.is_redirect:
                    raise WordPressError(
                        f"WordPress redirected to {response.headers.get('Location', 'another URL')}; "
                        "set WORDPRESS_BASE_URL to the site's canonical URL.",
                        status=response.status_code,
                    )
                if response.is_success:
                    return _json(response, repeatable)
                status = response.status_code
                if status in BLOCK_STATUSES:
                    raise _error(response, WordPressBlockedError)
                if status == 404:
                    raise _error(response, WordPressNotFoundError)
                if status not in RETRY_STATUSES or last or not repeatable:
                    raise _error(
                        response, WordPressError, may_have_succeeded=status in RETRY_STATUSES and not repeatable
                    )
            time.sleep(self._retry_sleep_ms * 2 ** (attempt - 1) / 1000)
        raise AssertionError("unreachable: the last attempt always returns or raises")


@contextmanager
def client() -> Iterator[WordPressClient]:
    """One authenticated connection, reused for every request in a run."""
    # No settings dict held here: it carries the application password, and this frame is a generator.
    retry_times, retry_sleep_ms = settings.WORDPRESS["retry_times"], settings.WORDPRESS["retry_sleep_ms"]
    with _http_client() as http:
        yield WordPressClient(http, retry_times=retry_times, retry_sleep_ms=retry_sleep_ms)


# Error pages and error trackers record each frame's locals; these hold the application password.
@sensitive_variables("config")
def _http_client() -> httpx.Client:
    config = settings.WORDPRESS
    missing = [name for key, name in REQUIRED_SETTINGS.items() if not config[key]]
    if missing:
        raise WordPressError(f"{', '.join(missing)} not set, so nothing was sent.")
    return httpx.Client(
        base_url=f"{config['base_url']}{API_PATH}",
        auth=httpx.BasicAuth(config["username"], config["app_password"]),
        headers={"User-Agent": settings.WIKIMEDIA["user_agent"], "Accept": "application/json"},
        timeout=httpx.Timeout(config["timeout"], write=config["upload_timeout"]),
        follow_redirects=False,
    )


def _json(response: httpx.Response, repeatable: bool):
    try:
        return response.json()
    except ValueError as error:
        # Often a caching or security plugin answering with an HTML page.
        raise WordPressError(
            "WordPress answered with a body that is not JSON.",
            status=response.status_code,
            response_excerpt=response.text[:RESPONSE_EXCERPT_CHARS],
            may_have_succeeded=not repeatable,
        ) from error


def _error(response: httpx.Response, kind: type[WordPressError], *, may_have_succeeded: bool = False) -> WordPressError:
    try:
        envelope = response.json()
    except ValueError:
        envelope = {}
    envelope = envelope if isinstance(envelope, dict) else {}
    retry_after = response.headers.get("Retry-After", "").strip()
    detail = envelope.get("message") or ""
    return kind(
        f"WordPress returned HTTP {response.status_code}" + (f": {detail}" if detail else "."),
        status=response.status_code,
        code=str(envelope.get("code") or ""),
        retry_after_seconds=int(retry_after) if retry_after.isdigit() else None,
        response_excerpt=response.text[:RESPONSE_EXCERPT_CHARS],
        may_have_succeeded=may_have_succeeded,
    )
