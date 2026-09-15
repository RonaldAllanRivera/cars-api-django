"""Builders for Commons API responses, shaped like the live formatversion=2 payloads."""

from collections.abc import Callable, Iterable

import httpx

Handler = Callable[[httpx.Request], httpx.Response]


def image_page(page_id: int, title: str, mime: str = "image/jpeg", extmetadata: dict | None = None) -> dict:
    return {
        "pageid": page_id,
        "title": title,
        "imageinfo": [
            {
                "url": f"https://example.com/{page_id}.jpg",
                "thumburl": f"https://example.com/{page_id}-thumb.jpg",
                "width": 800,
                "height": 600,
                "mime": mime,
                "extmetadata": extmetadata or {},
            }
        ],
    }


def pages(items: Iterable[dict], **extra) -> httpx.Response:
    return httpx.Response(200, json={**extra, "query": {"pages": list(items)}})


def category(title: str, files: int = 12, subcats: int = 1, redirect_to: str | None = None) -> dict:
    page = {"pageid": 1, "title": title, "categoryinfo": {"files": files, "subcats": subcats}}
    if redirect_to is not None:
        page["revisions"] = [{"slots": {"main": {"content": f"{{{{category redirect|{redirect_to}}}}}"}}}]
    return page


def missing(title: str) -> dict:
    return {"title": title, "missing": True}


def invalid(title: str) -> dict:
    return {
        "title": title,
        "invalidreason": 'The requested page title contains invalid characters: ">".',
        "invalid": True,
    }


def param(request: httpx.Request, name: str) -> str | None:
    return request.url.params.get(name)


def category_name(request: httpx.Request) -> str | None:
    """The probed category name, or None when the request is a file listing."""
    titles = param(request, "titles")
    return titles.removeprefix("Category:") if titles is not None else None


def existing_categories(names: Iterable[str], files: Handler | None = None) -> Handler:
    """Answers probes for `names` as populated categories, others as missing; file listings via `files`."""
    known = set(names)

    def handler(request: httpx.Request) -> httpx.Response:
        name = category_name(request)
        if name is None:
            return files(request) if files else pages([])
        title = f"Category:{name}"
        return pages([category(title) if name in known else missing(title)])

    return handler
