"""Resolves make/model to a Commons category, with the lookup cached."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.searches.models import CommonsCategoryLookup
from apps.searches.services.matching import category_candidates
from apps.searches.services.wikimedia import WikimediaClient


def locate_category(make: str, model: str | None, client: WikimediaClient | None = None) -> str | None:
    """The Commons category holding photographs of this model, or None.

    Answers are persisted per make/model: a hit forever, a miss for `category_miss_ttl_days`.
    A blank model resolves nothing, because the bare make is the whole marque.
    """
    if model is None or not model.strip():
        return None

    lookup = CommonsCategoryLookup.objects.filter(make=make, model=model).first()
    if lookup is not None and not _is_stale_miss(lookup):
        return lookup.category

    client = client or WikimediaClient()
    resolved = None
    for candidate in category_candidates(make, model):
        # Store what Commons resolves to (e.g. "Ford F-150"), not the candidate we guessed.
        resolved = client.resolve_category(candidate)
        if resolved is not None:
            break

    CommonsCategoryLookup.objects.update_or_create(
        make=make, model=model, defaults={"category": resolved, "checked_at": timezone.now()}
    )
    return resolved


def _is_stale_miss(lookup: CommonsCategoryLookup) -> bool:
    if lookup.category is not None:
        return False
    ttl = timedelta(days=int(settings.WIKIMEDIA["category_miss_ttl_days"]))
    return lookup.checked_at is None or lookup.checked_at < timezone.now() - ttl
