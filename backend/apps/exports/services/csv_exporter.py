"""Writes the CSV manifest that accompanies a batch ZIP."""

from collections.abc import Iterable, Iterator

from apps.exports.services.filenames import BaseNameSequence, extension_from_url
from apps.images.models import CarImage

HEADER = ["Year", "Make", "Model", "Transmission", "Filename", "SourceUrl", "SearchId", "ImageId"]


def export_rows(images: Iterable[CarImage]) -> Iterator[list[str]]:
    """
    Yields HEADER, then one row per image. Filenames are numbered exactly as
    the ZIP numbers them. Select `car_search` up front to avoid a query per row.
    """
    yield HEADER
    names = BaseNameSequence()
    for image in images:
        search = image.car_search if image.car_search_id else None
        yield [
            str(image.year),
            image.make or "",
            image.model or "",
            (search.transmission if search else None) or "",
            names.next(image.year, image.make, image.model, extension_from_url(image.source_url)),
            image.source_url or "",
            str(image.car_search_id or ""),
            str(image.pk),
        ]
