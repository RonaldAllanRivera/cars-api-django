"""
Signed, expiring export links.

The app hands the link to the system browser, which follows it with no bearer
token, so the signature is the credential. The filters stay readable in the
query string and are covered by an HMAC over every parameter, so editing any
of them (or the expiry, or the nonce) invalidates the link.

ZIP links are also single-use: a nonce is written to the cache when the link
is minted and consumed atomically (`cache.delete` reports whether it removed
the key) when it is followed, because replaying one costs up to a hundred
Wikimedia fetches.
"""

import secrets
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare

SALT = "api.v1.exports.download"
LINK_PARAMS = ("format", "nonce", "expires", "signature")


def _signature(params: dict[str, str]) -> str:
    canonical = urlencode(sorted(params.items()), quote_via=quote)
    return signing.Signer(salt=SALT).signature(canonical)


def _nonce_key(nonce: str) -> str:
    return f"export-nonce:{nonce}"


def mint(request, export_format: str, filters: dict[str, str]) -> tuple[str, datetime]:
    """An absolute signed download URL, and when it stops working."""
    ttl = settings.CARS_IMAGES["export_link_ttl_seconds"]
    expires_at = timezone.now().replace(microsecond=0) + timedelta(seconds=ttl)

    params = {"format": export_format, **filters}
    if export_format == "zip":
        nonce = secrets.token_urlsafe(30)
        cache.add(_nonce_key(nonce), True, timeout=ttl)
        params["nonce"] = nonce
    params["expires"] = str(int(expires_at.timestamp()))
    params["signature"] = _signature(params)

    url = request.build_absolute_uri(reverse("exports-download"))
    return f"{url}?{urlencode(params, quote_via=quote)}", expires_at


def verify(query: QueryDict) -> bool:
    """True for an untampered, unexpired link. A repeated parameter is tampering."""
    if any(len(values) != 1 for _, values in query.lists()):
        return False
    params = query.dict()
    signature = params.pop("signature", "")
    if not constant_time_compare(signature, _signature(params)):
        return False
    try:
        return int(params.get("expires", "")) > timezone.now().timestamp()
    except ValueError:
        return False


def consume_nonce(nonce: str | None) -> bool:
    """Atomically use up a ZIP link's nonce; False if it was never minted or already used."""
    return bool(nonce) and cache.delete(_nonce_key(nonce))


def filters_from(query: QueryDict) -> dict[str, str]:
    """The image filters carried by a link, without the link's own parameters."""
    return {key: value for key, value in query.dict().items() if key not in LINK_PARAMS}
