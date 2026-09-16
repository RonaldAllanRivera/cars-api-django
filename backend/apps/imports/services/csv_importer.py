"""
Turns an uploaded Make/Model/Year CSV into one pending single-year CarSearch
per unique combination.
"""

import csv
import io
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.searches.models import CarSearch

REQUIRED_COLUMNS = ("Make", "Model", "Year")
MIN_YEAR = 1900
INSERT_BATCH_SIZE = 500


class CsvImportError(Exception):
    """Upload-level rejection; the message is shown to the user."""


@dataclass
class CsvImportResult:
    csv_import: CsvImport
    skipped_invalid_rows: int


@dataclass(frozen=True)
class _Combo:
    year: int
    make: str
    model: str
    transmission: str | None


@dataclass(frozen=True)
class _RejectedRow:
    row_number: int
    raw_row: str
    reason: str


def import_csv(uploaded_file, user) -> CsvImportResult:
    """`uploaded_file` is a Django UploadedFile (has .name and .read())."""
    try:
        return _run_import(uploaded_file, user)
    except CsvImportError as exc:
        # A rejected upload never becomes a CsvImport, so the filename is the only handle on it.
        error_logger.record(ErrorEvent.Context.CSV_UPLOAD, exc, details={"filename": uploaded_file.name})
        raise


def _run_import(uploaded_file, user) -> CsvImportResult:
    rows = csv.reader(io.StringIO(_read_text(uploaded_file), newline=""))
    try:
        headers = next(rows, None)
        if headers is None:
            raise CsvImportError("CSV is empty.")

        headers = [header.strip() for header in headers]
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            raise CsvImportError(f"Missing required columns: {', '.join(missing)}. Required: Make, Model, Year.")

        index = {name: position for position, name in enumerate(headers)}
        max_year = timezone.localdate().year + 1
        total_rows = 0
        rejected: list[_RejectedRow] = []
        combos: dict[str, _Combo] = {}

        for row in rows:
            total_rows += 1
            make, model, year = (_cell(row, index[column]) for column in REQUIRED_COLUMNS)

            reason = _rejection_reason(make, model, year, max_year)
            if reason is not None:
                rejected.append(_RejectedRow(total_rows, ",".join(row), reason))
                continue

            key = f"{int(year)}|{make}|{model}"
            if key not in combos:
                transmission = _cell(row, index["Transmission"]) if "Transmission" in index else ""
                combos[key] = _Combo(int(year), make, model, transmission or None)
    except csv.Error as exc:
        raise CsvImportError(f"CSV could not be parsed: {exc}.") from exc

    unique_count = len(combos)
    max_combos = settings.CARS_IMAGES["csv_import_max_combos"]
    if unique_count > max_combos:
        raise CsvImportError(
            f"CSV produces {unique_count} unique queries, which exceeds the limit of {max_combos}. "
            "Split the CSV externally and retry."
        )

    # The combo cap bounds queries, not images: raising images-per-year could
    # otherwise commit a run to many times more downloads than intended.
    images_per_year = settings.CARS_IMAGES["csv_import_default_images_per_year"]
    projected_images = unique_count * images_per_year
    max_projected_images = settings.CARS_IMAGES["csv_import_max_projected_images"]
    if projected_images > max_projected_images:
        raise CsvImportError(
            f"CSV produces {unique_count} unique queries x {images_per_year} images = {projected_images} "
            f"image downloads, which exceeds the API download limit of {max_projected_images}. "
            "Split the CSV, or lower CSV_IMPORT_DEFAULT_IMAGES_PER_YEAR, and retry."
        )

    with transaction.atomic():
        csv_import = CsvImport.objects.create(
            original_filename=uploaded_file.name,
            total_rows=total_rows,
            unique_combos=unique_count,
            duplicates_skipped=total_rows - unique_count - len(rejected),
            imported_by=user,
        )
        CarSearch.objects.bulk_create(
            (
                CarSearch(
                    make=combo.make,
                    model=combo.model,
                    from_year=combo.year,
                    to_year=combo.year,
                    transmission=combo.transmission,
                    images_per_year=images_per_year,
                    status=CarSearch.Status.PENDING,
                    requested_by=user,
                    csv_import=csv_import,
                )
                for combo in combos.values()
            ),
            batch_size=INSERT_BATCH_SIZE,
        )

    # Logged only once the import exists, so each rejection can link to it.
    for row in rejected:
        error_logger.record(
            ErrorEvent.Context.CSV_ROW,
            row.reason,
            csv_import=csv_import,
            details={"row_number": row.row_number, "raw_row": row.raw_row},
            severity=ErrorEvent.Severity.WARNING,
        )

    return CsvImportResult(csv_import=csv_import, skipped_invalid_rows=len(rejected))


def _read_text(uploaded_file) -> str:
    try:
        uploaded_file.seek(0)
        raw = uploaded_file.read()
    except (OSError, ValueError) as exc:
        raise CsvImportError("Unable to open uploaded CSV.") from exc
    if isinstance(raw, str):
        return raw.removeprefix("\ufeff")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvImportError('CSV must be UTF-8 encoded. Re-save it as "CSV UTF-8" and retry.') from exc


def _cell(row: list[str], position: int) -> str:
    return row[position].strip() if position < len(row) else ""


def _rejection_reason(make: str, model: str, year: str, max_year: int) -> str | None:
    """Why a row cannot become a query, in words the operator can act on; None if it can."""
    missing = [name for name, value in zip(REQUIRED_COLUMNS, (make, model, year), strict=True) if not value]
    if missing:
        return f"{', '.join(missing)} missing."
    if not (year.isascii() and year.isdigit()):
        return f"Year '{year}' is not a number."
    if not MIN_YEAR <= int(year) <= max_year:
        return f"Year {int(year)} is outside the accepted range {MIN_YEAR}-{max_year}."
    return None
