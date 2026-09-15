"""Port of FilenameBuilder: deterministic, filesystem-safe "YEAR MAKE MODEL.ext" names."""

import re
from posixpath import splitext
from urllib.parse import urlsplit

UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')
MAX_BASE_LENGTH = 200
DEFAULT_EXTENSION = "jpg"


def build_filename(year: int, make: str, model: str | None, extension: str | None) -> str:
    """e.g. "1997 Toyota RAV4.jpg"; the base is capped at 200 characters."""
    base = f"{int(year)} {make or ''} {model or ''}"
    base = UNSAFE_CHARS.sub(" - ", base)
    base = re.sub(r"\s+", " ", base).strip()[:MAX_BASE_LENGTH]
    extension = re.sub(r"[^a-z0-9]", "", (extension or "").lower()) or DEFAULT_EXTENSION
    return f"{base}.{extension}"


def _with_suffix(filename: str, suffix: int) -> str:
    base, dot, extension = filename.rpartition(".")
    return f"{base} {suffix}{dot}{extension}"


def build_ranked(year: int, make: str, model: str | None, extension: str | None, rank: int) -> str:
    """Rank 1 is the bare name; rank N appends " N" before the extension."""
    candidate = build_filename(year, make, model, extension)
    return candidate if rank <= 1 else _with_suffix(candidate, rank)


def build_unique(year: int, make: str, model: str | None, extension: str | None, used: set[str]) -> str:
    """First free name of "BASE.ext", "BASE 2.ext", "BASE 3.ext", ...; records it in `used`."""
    candidate = first = build_filename(year, make, model, extension)
    counter = 2
    while candidate in used:
        candidate = _with_suffix(first, counter)
        counter += 1
    used.add(candidate)
    return candidate


class BaseNameSequence:
    """
    Names for a batch export, numbered per base name regardless of extension,
    so "1997 Toyota RAV4.jpg" is followed by "1997 Toyota RAV4 2.png".
    The ZIP and the CSV manifest both use it so their filenames agree.
    """

    def __init__(self) -> None:
        self._next_counter: dict[str, int] = {}

    def next(self, year: int, make: str, model: str | None, extension: str | None) -> str:
        filename = build_filename(year, make, model, extension)
        base = filename.rpartition(".")[0]
        counter = self._next_counter.get(base)
        self._next_counter[base] = (counter or 1) + 1
        return filename if counter is None else _with_suffix(filename, counter)


def extension_from_url(url: str) -> str:
    """The extension of the URL's path (without the dot), or "jpg" when there is none."""
    extension = splitext(urlsplit(url or "").path)[1]
    return extension[1:] or DEFAULT_EXTENSION
