"""
Fills whichever SEO fields the model left empty, and bounds the ones it wrote.

The WordPress plugin repeats these fallbacks in three places. They live here
once, as a pure function, so every path that saves a post gets identical results.
"""

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass

from django.utils.html import strip_tags

# What search results display before truncating.
SEO_TITLE_LENGTH = 60
SEO_DESCRIPTION_LENGTH = 160
DERIVED_KEYWORD_COUNT = 6

# The plugin's SEO editor refuses anything longer, so a runaway model value is cut
# to what an editor could have typed.
SEO_TITLE_MAX = 120
SEO_DESCRIPTION_MAX = 320
SEO_KEYWORDS_MAX = 255

KEYWORD_SEPARATOR = ", "
# Hyphen, en dash and em dash: a cut that ends on one reads as unfinished.
TRAILING_PUNCTUATION = " ,;:-\u2013\u2014"
FIRST_PARAGRAPH = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class SeoFields:
    seo_title: str
    seo_description: str
    seo_keywords: str


def fill_gaps(
    *,
    title: str,
    content: str,
    seo_title: str,
    seo_description: str,
    seo_keywords: Iterable[str],
    year: int,
    make: str,
    model: str | None,
) -> SeoFields:
    vehicle = _squash(" ".join(str(part) for part in (year, make, model) if part))

    written_title = _squash(seo_title)
    written_description = _squash(seo_description)
    written_keywords = _unique(seo_keywords)

    return SeoFields(
        seo_title=_shorten(written_title, SEO_TITLE_MAX)
        if written_title
        else _shorten(_squash(title) or vehicle, SEO_TITLE_LENGTH),
        seo_description=_shorten(written_description, SEO_DESCRIPTION_MAX)
        if written_description
        else _shorten(_summary(content), SEO_DESCRIPTION_LENGTH),
        seo_keywords=_join_within(
            written_keywords or _derived_keywords(year, make, model)[:DERIVED_KEYWORD_COUNT], SEO_KEYWORDS_MAX
        ),
    )


def _summary(content: str) -> str:
    """
    The intro paragraph as plain text. The article opens with a linked
    sub-headline, which makes a poor description, so the first <p> wins.
    """
    match = FIRST_PARAGRAPH.search(content or "")
    return _plain_text(match.group(1) if match else content or "")


def _plain_text(markup: str) -> str:
    # strip_tags removes a tag without leaving a gap, so "<h2>A</h2><p>B</p>" would read "AB".
    return _squash(html.unescape(strip_tags(markup.replace("<", " <"))))


def _derived_keywords(year: int, make: str, model: str | None) -> list[str]:
    make, model = _squash(make), _squash(model)
    candidates = [
        f"{year} {make} {model}",
        f"{make} {model}",
        f"used {make}",
        f"used {model}" if model else "",
        f"{make} {model} for sale",
    ]
    return _unique(candidates)


def _unique(values: Iterable[str]) -> list[str]:
    """Squashed, blanks dropped, first spelling kept when two differ only by case."""
    seen: set[str] = set()
    kept = []
    for value in values or ():
        text = _squash(value)
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            kept.append(text)
    return kept


def _join_within(keywords: list[str], limit: int) -> str:
    """Whole keywords only: a keyword cut in half is a different, meaningless keyword."""
    joined = ""
    for keyword in keywords:
        candidate = f"{joined}{KEYWORD_SEPARATOR}{keyword}" if joined else keyword
        if len(candidate) > limit:
            break
        joined = candidate
    return joined


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    # One character past the limit reveals whether the cut already falls between words.
    boundary = text.rfind(" ", 0, limit + 1)
    cut = text[:boundary] if boundary > 0 else text[:limit]
    return cut.rstrip(TRAILING_PUNCTUATION)


def _squash(value: str | None) -> str:
    return " ".join(str(value or "").split())
