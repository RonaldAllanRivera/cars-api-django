"""
Queues one blog post per vehicle that has approved images.

Seeding spends nothing: it only creates pending BlogPost rows for the publisher
to work through. A vehicle is identified by its slug, so "Toyota RAV4" and
" toyota rav4" found by two different searches are one post, and running it
again never duplicates or alters an existing post.
"""

from dataclasses import dataclass

from django.db.models import QuerySet
from django.utils.text import slugify

from apps.images.models import CarImage
from apps.publishing.models import BlogPost

SLUG_MAX_LENGTH = BlogPost._meta.get_field("slug").max_length


@dataclass
class SeedResult:
    created: int = 0
    existing: int = 0


def vehicle_slug(year: int, make: str, model: str | None) -> str:
    """ "1997-toyota-rav4": the post's identity here and its slug on WordPress."""
    # slugify lowercases, strips accents and collapses whitespace, so spelling variants meet.
    return slugify(f"{int(year)} {make or ''} {model or ''}")[:SLUG_MAX_LENGTH].rstrip("-")


def sync_posts(images: QuerySet[CarImage] | None = None, *, csv_import=None, requested_by=None) -> SeedResult:
    """
    Create a pending post for each vehicle among the approved images, optionally
    limited to a selection or one import. A post takes its spelling and links
    from the vehicle's earliest approved image.
    """
    queryset = (images if images is not None else CarImage.objects.all()).filter(
        review_status=CarImage.ReviewStatus.APPROVED
    )
    if csv_import is not None:
        queryset = queryset.filter(car_search__csv_import=csv_import)

    first_by_slug: dict[str, tuple] = {}
    rows = queryset.order_by("id").values_list("year", "make", "model", "car_search_id", "car_search__csv_import_id")
    for year, make, model, car_search_id, csv_import_id in rows.iterator():
        first_by_slug.setdefault(vehicle_slug(year, make, model), (year, make, model, car_search_id, csv_import_id))

    result = SeedResult()
    for slug, (year, make, model, car_search_id, csv_import_id) in first_by_slug.items():
        _, created = BlogPost.objects.get_or_create(
            slug=slug,
            defaults={
                "year": year,
                "make": " ".join(make.split()),
                # A blank model is stored as NULL, like a missing one.
                "model": " ".join((model or "").split()) or None,
                "car_search_id": car_search_id,
                "csv_import_id": csv_import_id,
                "requested_by": requested_by,
            },
        )
        if created:
            result.created += 1
        else:
            result.existing += 1
    return result
