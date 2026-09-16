"""Pure text rules: search-term normalisation, category resolution, year
matching and make-relevance checking.

Patterns that must not match non-ASCII look-alikes are compiled with re.ASCII;
the rest keep Python's Unicode classes.
"""

import re

from django.utils import timezone
from django.utils.html import strip_tags

_DISPLACEMENT_PREFIX = re.compile(r"^\d+\.\d+\s*", re.ASCII)

# Tokens the EPA vehicle CSV carries that Commons category names never do.
QUALIFIERS = (
    "AWD", "4WD", "2WD", "FWD", "RWD", "xDrive", "sDrive", "quattro", "4MATIC",
    "FFV", "MHEV", "PHEV", "EcoDiesel", "LWB", "SWB", "Pickup", "Truck", "Van",
    "Wagon", "Convertible", "Cabriolet", "Roadster", "Coupe", "Sedan",
    "Hatchback", "Hardtop", "Gran Turismo", "Gran Coupe", "New",
)  # fmt: skip

_QUALIFIER_PATTERN = re.compile(r"\b(?:" + "|".join(map(re.escape, QUALIFIERS)) + r")\b", re.IGNORECASE)
_DOORS_AND_WHEELS = re.compile(r"\b\d+\s*(?:door|inch\s+Wheels)\b", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\([^)]*\)")
_WHITESPACE = re.compile(r"\s+", re.ASCII)
# Characters MediaWiki refuses in a page title; it answers {"invalid": true} with no "missing" key.
_ILLEGAL_TITLE_CHARS = re.compile(r"[#<>\[\]|{}]")

# Capture dates in the forms Commons filenames use: "01-28-2010", "8.2.20", "2017.1.23", "2024 08 24".
_PHOTO_DATE = re.compile(
    r"(?<!\d)(?:\d{1,2}[-./]\d{1,2}[-./]\d{2,4}|\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{4}[ _]\d{1,2}[ _]\d{1,2})(?!\d)",
    re.ASCII,
)
# "1997-1999", "1998-99", "'98-'99": a range names no single model year.
_YEAR_RANGE = re.compile(r"(?<!\d)(?:\d{4}|'\d{2})\s*[-\N{EN DASH}\N{EM DASH}]\s*'?\d{2,4}(?!\d)")
_FILE_PREFIX = re.compile(r"^File:", re.IGNORECASE)
_LEADING_YEAR = re.compile(r"^\s*(\d{4})\b", re.ASCII)
EARLIEST_MODEL_YEAR = 1885


def normalize_model(model: str) -> str:
    """Collapse "2.2CL/3.0CL" to "CL": strip a leading displacement unless that leaves under 2 chars."""
    normalized: list[str] = []
    for segment in model.split("/"):
        original = segment.strip()
        if not original:
            continue
        stripped = _DISPLACEMENT_PREFIX.sub("", original, count=1).strip()
        candidate = stripped if len(stripped) >= 2 else original
        if candidate not in normalized:
            normalized.append(candidate)
    return " ".join(normalized)


def category_candidates(make: str, model: str) -> list[str]:
    """Candidate Commons category names, most specific first. The bare make is never offered."""
    base = _collapse(_PARENTHETICAL.sub(" ", normalize_model(model)))
    stripped = _strip_qualifiers(base)

    # Both token lists are shrunk: a model starting with a qualifier ("New Beetle")
    # would otherwise lose its own category to the broader one ("Beetle").
    names: list[str] = []
    for source in (base, stripped):
        _push(names, source)
        tokens = source.split(" ") if source else []
        for length in range(len(tokens) - 1, 0, -1):
            _push(names, " ".join(tokens[:length]))

    # Stable sort, so equal-specificity names keep insertion order.
    names.sort(key=lambda name: name.count(" "), reverse=True)

    titles = (f"{make.strip()} {name}" for name in names)
    return [title for title in titles if not _ILLEGAL_TITLE_CHARS.search(title)]


def model_year(title: str, make: str) -> int | None:
    """The single model year a Commons file title asserts, or None."""
    text = _FILE_PREFIX.sub("", title, count=1)
    text = _PHOTO_DATE.sub(" ", text)

    if _YEAR_RANGE.search(text):
        return None

    make_pattern = _make_pattern(make)
    if not make_pattern:
        return None

    # The year right before the make is the strongest assertion, so it wins over a leading event year.
    if match := re.search(r"(?<!\d)(\d{4})\s+" + make_pattern, text, re.IGNORECASE):
        return _plausible(int(match.group(1)))

    # A leading year counts only when the make is corroborated somewhere in the title.
    if (match := _LEADING_YEAR.search(text)) and re.search(make_pattern, text, re.IGNORECASE):
        return _plausible(int(match.group(1)))

    return None


def is_make_confirmed(make: str, title: str | None, description: str | None, categories: str | None) -> bool:
    """Case-insensitive substring test for the make across title, description (HTML stripped) and categories."""
    needle = (make or "").strip().lower()
    if not needle:
        return False

    haystack = " ".join([title or "", strip_tags(description or ""), categories or ""]).strip().lower()
    if not haystack:
        return False

    return needle in haystack


def _push(names: list[str], candidate: str) -> None:
    candidate = _collapse(candidate).strip(" -")
    if candidate and candidate not in names:
        names.append(candidate)


def _strip_qualifiers(value: str) -> str:
    value = _QUALIFIER_PATTERN.sub(" ", value)
    value = _DOORS_AND_WHEELS.sub(" ", value)
    return _collapse(value)


def _collapse(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


def _make_pattern(make: str) -> str:
    """The make as a regex fragment in which hyphens and spaces are interchangeable."""
    make = make.strip()
    if not make:
        return ""
    return r"[-\s]+".join(re.escape(part) for part in re.split(r"[- ]", make))


def _plausible(year: int) -> int | None:
    return year if EARLIEST_MODEL_YEAR <= year <= timezone.now().year + 2 else None
