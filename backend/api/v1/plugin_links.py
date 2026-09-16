"""
Signed, expiring, single-use links to download the WordPress plugin.

The browser follows the link with no bearer token, so the signature is the
credential: a timestamped token (django.core.signing) that expires with the
export link TTL, carrying a nonce that is consumed atomically on first use.
"""

import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

SALT = "api.v1.wordpress_plugin.download"
VALID, INVALID, USED = "valid", "invalid", "used"


def _ttl() -> int:
    return settings.CARS_IMAGES["export_link_ttl_seconds"]


def _nonce_key(nonce: str) -> str:
    return f"plugin-download-nonce:{nonce}"


def mint(request) -> tuple[str, datetime]:
    """An absolute download URL, and when it stops working."""
    nonce = secrets.token_urlsafe(30)
    cache.add(_nonce_key(nonce), True, timeout=_ttl())
    token = signing.dumps({"nonce": nonce}, salt=SALT)
    url = request.build_absolute_uri(reverse("wordpress-plugin-download"))
    return f"{url}?{urlencode({'token': token})}", timezone.now().replace(microsecond=0) + timedelta(seconds=_ttl())


def redeem(token: str) -> str:
    """VALID once for an untampered, unexpired link; USED after that; INVALID otherwise."""
    try:
        payload = signing.loads(token, salt=SALT, max_age=_ttl())
    except signing.BadSignature:  # SignatureExpired is a BadSignature too
        return INVALID
    nonce = payload.get("nonce") if isinstance(payload, dict) else None
    if not nonce:
        return INVALID
    # cache.delete reports whether it removed the key, so two racing requests cannot both win.
    return VALID if cache.delete(_nonce_key(nonce)) else USED
