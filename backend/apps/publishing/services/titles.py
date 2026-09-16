"""
Wikimedia Commons file titles, made fit for a reader.

A port of web/src/format/imageTitle.ts, so an image is named the same way in the
review queue and in a published post.
"""

import re

_PREFIX = re.compile(r"^file:", re.IGNORECASE)
_EXTENSION = re.compile(r"\.(jpe?g|png|gif|webp|tiff?|svg)\Z", re.IGNORECASE)
# Commons' duplicate marker is a bare integer; "(Geneva)" is real content.
_DISAMBIGUATOR = re.compile(r"\s*\(\d+\)\Z")


def clean_title(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = _DISAMBIGUATOR.sub("", _EXTENSION.sub("", _PREFIX.sub("", raw))).replace("_", " ").strip()
    # An empty string would render as a blank line where a title should be.
    return cleaned or None
