"""
Port of ImportCoverage: how much of a CSV import has actually been searched.

The images list alone cannot tell a run that stopped early from one that
finished and found little; counting the searches behind it can.
"""

from django.db.models import Count, Exists, OuterRef, Q

from apps.images.models import CarImage
from apps.searches.models import CarSearch

# No worker runs searches in the background, so a `running` row is a request
# that died mid-search: still work to do.
NOT_RUN_STATUSES = (CarSearch.Status.PENDING, CarSearch.Status.RUNNING)


def import_coverage(csv_import_id: int | None = None) -> dict | None:
    """
    {total, searched, not_run, failed, with_images, no_images} for one import,
    or across every CSV-derived search when `csv_import_id` is None. None when
    total is 0, so callers show nothing rather than a row of zeroes.
    """
    searches = CarSearch.objects.filter(csv_import__isnull=False)
    if csv_import_id is not None:
        searches = searches.filter(csv_import_id=csv_import_id)

    counts = searches.annotate(
        has_images=Exists(CarImage.objects.filter(car_search=OuterRef("pk"))),
    ).aggregate(
        total=Count("pk"),
        not_run=Count("pk", filter=Q(status__in=NOT_RUN_STATUSES)),
        failed=Count("pk", filter=Q(status=CarSearch.Status.FAILED)),
        with_images=Count("pk", filter=Q(has_images=True)),
        no_images=Count("pk", filter=Q(status=CarSearch.Status.COMPLETED, has_images=False)),
    )
    if counts["total"] == 0:
        return None

    return {
        "total": counts["total"],
        # A failed search still ran, so it counts as searched.
        "searched": counts["total"] - counts["not_run"],
        "not_run": counts["not_run"],
        "failed": counts["failed"],
        "with_images": counts["with_images"],
        "no_images": counts["no_images"],
    }
