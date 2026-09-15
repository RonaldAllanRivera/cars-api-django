"""Port of CarImageSearchService."""

from django.db import transaction

from apps.images.models import CarImage
from apps.searches.models import CarSearch
from apps.searches.services.category_locator import locate_category
from apps.searches.services.matching import is_make_confirmed, model_year
from apps.searches.services.wikimedia import WikimediaClient

SEARCH_FIELDS = (
    "make",
    "model",
    "from_year",
    "to_year",
    "color",
    "transmission",
    "transparent_background",
    "images_per_year",
)
# What an omitted optional field means when matching an existing search.
_MATCH_DEFAULTS = {
    "model": None,
    "color": None,
    "transmission": None,
    "transparent_background": False,
    "images_per_year": 10,
}


def create_search(*, requested_by, csv_import=None, **fields) -> CarSearch:
    """Swaps reversed years; status pending. `fields` are SEARCH_FIELDS."""
    _reject_unknown(fields)
    if fields["from_year"] > fields["to_year"]:
        fields["from_year"], fields["to_year"] = fields["to_year"], fields["from_year"]
    return CarSearch.objects.create(
        requested_by=requested_by, csv_import=csv_import, status=CarSearch.Status.PENDING, **fields
    )


def find_existing_completed_search(**fields) -> CarSearch | None:
    """Exact match on all SEARCH_FIELDS with status completed, newest first."""
    _reject_unknown(fields)
    criteria = {**_MATCH_DEFAULTS, **fields}
    return (
        CarSearch.objects.filter(status=CarSearch.Status.COMPLETED, **{name: criteria[name] for name in SEARCH_FIELDS})
        .order_by("-created_at", "-id")
        .first()
    )


def run_search(search: CarSearch, client: WikimediaClient | None = None) -> CarSearch:
    """Fetch and store exact-year images. Failures roll back and propagate; the caller marks the search failed."""
    client = client or WikimediaClient()
    # Resolved before the transaction: the lookup row is cache state and must survive a failed run.
    category = locate_category(search.make, search.model, client)

    with transaction.atomic():
        _execute(search, category, client)
    return search


def refresh_search(search: CarSearch, client: WikimediaClient | None = None) -> CarSearch:
    """Delete the search's images and fetch them again, atomically; on any error mark it failed and re-raise."""
    client = client or WikimediaClient()
    try:
        # Inside the try, because resolving talks to Commons and a block here must mark the search failed too.
        category = locate_category(search.make, search.model, client)
        if category is not None:
            for year in range(search.from_year, search.to_year + 1):
                client.forget_category(category, year)

        # Delete and refetch share one transaction, so a failed refetch restores the old images.
        with transaction.atomic():
            CarImage.objects.filter(car_search_id=search.pk).delete()
            search.refresh_from_db()
            _execute(search, category, client)
    except Exception:
        mark_failed(search)
        raise
    return search


def mark_failed(search: CarSearch) -> None:
    """Force a terminal `failed` status, outside whatever transaction just rolled back."""
    search.status = CarSearch.Status.FAILED
    search.save(update_fields=["status", "updated_at"])


def _execute(search: CarSearch, category: str | None, client: WikimediaClient) -> None:
    # commons_category tells an unresolvable model (null) apart from a category with no photo of that year.
    search.status = CarSearch.Status.RUNNING
    search.commons_category = category
    search.save(update_fields=["status", "commons_category", "updated_at"])

    for year in range(search.from_year, search.to_year + 1):
        _fetch_and_store_for_year(search, category, year, client)

    search.status = CarSearch.Status.COMPLETED
    search.save(update_fields=["status", "updated_at"])


def _fetch_and_store_for_year(search: CarSearch, category: str | None, year: int, client: WikimediaClient) -> None:
    if category is None:
        return

    # Whole category, then the year filter, then the limit: limiting the fetch would hand the filter a slice.
    matching = [
        file for file in client.files_in_category(category, year) if model_year(file["title"], search.make) == year
    ][: search.images_per_year]

    for file in matching:
        # Ownership (search, year) is part of the key, so a file answering two searches is copied, not moved.
        CarImage.objects.update_or_create(
            car_search=search,
            year=year,
            provider=file["provider"],
            provider_image_id=file["provider_image_id"],
            defaults={
                "make": search.make,
                "model": search.model,
                "color": search.color,
                "transparent_background": search.transparent_background,
                "title": file["title"],
                "description": file["description"],
                "source_url": file["source_url"],
                "thumbnail_url": file["thumbnail_url"],
                "width": file["width"],
                "height": file["height"],
                "license": file["license"],
                "attribution": file["attribution"],
                "make_confirmed": is_make_confirmed(
                    search.make, file["title"], file["description"], _categories_of(file)
                ),
                # Exact-year by construction: the file's own title names this year.
                "year_confirmed": True,
                "download_status": CarImage.DownloadStatus.NOT_DOWNLOADED,
                "download_path": None,
                "metadata": file["metadata"],
            },
        )


def _categories_of(file: dict) -> str | None:
    try:
        return file["metadata"]["imageinfo"][0]["extmetadata"]["Categories"]["value"]
    except (KeyError, IndexError, TypeError):
        return None


def _reject_unknown(fields: dict) -> None:
    if unknown := sorted(set(fields) - set(SEARCH_FIELDS)):
        raise TypeError(f"Unexpected search fields: {', '.join(unknown)}")
