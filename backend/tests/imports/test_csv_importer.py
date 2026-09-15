import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.imports.models import CsvImport
from apps.imports.services.csv_importer import CsvImportError, CsvImportResult, import_csv
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def make_csv(content: str | bytes, name: str = "sample.csv") -> SimpleUploadedFile:
    data = content.encode() if isinstance(content, str) else content
    return SimpleUploadedFile(name, data, content_type="text/csv")


THREE_COMBOS = "Make,Model,Year,Transmission\nToyota,RAV4,1997,A\nToyota,Camry,1998,B\nHonda,Civic,2010,C\n"


@pytest.fixture
def user():
    return UserFactory()


def test_imports_unique_year_make_model_rows(user):
    csv = make_csv(
        "Make,Model,Year,Transmission\n"
        "Toyota,RAV4,1997,Automatic 4-spd\n"
        "Toyota,Camry,1998,Manual 5-spd\n"
        "Mitsubishi,Mirage,2015,Automatic\n"
    )

    result = import_csv(csv, user)

    assert isinstance(result, CsvImportResult)
    assert isinstance(result.csv_import, CsvImport)
    assert result.csv_import.total_rows == 3
    assert result.csv_import.unique_combos == 3
    assert result.csv_import.duplicates_skipped == 0
    assert result.csv_import.original_filename == "sample.csv"
    assert result.csv_import.imported_by == user
    assert result.skipped_invalid_rows == 0
    assert CarSearch.objects.count() == 3
    assert CarSearch.objects.filter(csv_import=result.csv_import).count() == 3


def test_deduplicates_by_year_make_model_ignoring_transmission(user):
    csv = make_csv(
        "Make,Model,Year,Transmission\n"
        "Toyota,RAV4,1997,Automatic 4-spd\n"
        "Toyota,RAV4,1997,Manual 5-spd\n"
        "Toyota,RAV4,1997,Automatic 4-spd\n"
    )

    result = import_csv(csv, user)

    assert result.csv_import.total_rows == 3
    assert result.csv_import.unique_combos == 1
    assert result.csv_import.duplicates_skipped == 2
    assert CarSearch.objects.count() == 1


def test_sets_from_year_and_to_year_to_same_value(user, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "csv_import_default_images_per_year": 5}

    import_csv(make_csv("Make,Model,Year,Transmission\nHonda,Civic,2010,Manual\n"), user)

    search = CarSearch.objects.get()
    assert search.from_year == 2010
    assert search.to_year == 2010
    assert search.make == "Honda"
    assert search.model == "Civic"
    assert search.status == CarSearch.Status.PENDING
    assert search.images_per_year == 5
    assert search.requested_by == user
    assert search.color is None
    assert search.transparent_background is False


def test_rejects_when_unique_combos_exceeds_max(user, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "csv_import_max_combos": 2}

    with pytest.raises(CsvImportError) as excinfo:
        import_csv(make_csv(THREE_COMBOS), user)

    assert str(excinfo.value) == (
        "CSV produces 3 unique queries, which exceeds the limit of 2. Split the CSV externally and retry."
    )
    assert CsvImport.objects.count() == 0
    assert CarSearch.objects.count() == 0


def test_skips_rows_with_invalid_year(user):
    csv = make_csv("Make,Model,Year,Transmission\nToyota,RAV4,1997,A\nToyota,Camry,abc,B\nHonda,Civic,1800,C\n")

    result = import_csv(csv, user)

    assert CarSearch.objects.count() == 1
    assert result.skipped_invalid_rows == 2
    assert result.csv_import.total_rows == 3
    assert result.csv_import.duplicates_skipped == 0


def test_rejects_missing_required_columns(user):
    with pytest.raises(CsvImportError) as excinfo:
        import_csv(make_csv("Make,Year,Transmission\nToyota,1997,A\n"), user)

    assert str(excinfo.value) == "Missing required columns: Model. Required: Make, Model, Year."


def test_lists_every_missing_column_in_required_order(user):
    with pytest.raises(CsvImportError, match=r"^Missing required columns: Make, Model, Year\. "):
        import_csv(make_csv("Colour,Size\nred,large\n"), user)


def test_rejects_an_empty_file(user):
    with pytest.raises(CsvImportError, match=r"^CSV is empty\.$"):
        import_csv(make_csv(""), user)


def test_header_names_are_trimmed_and_transmission_is_optional(user):
    result = import_csv(make_csv(" Model , Year ,Make\nRAV4,1997,Toyota\n"), user)

    search = CarSearch.objects.get()
    assert (search.make, search.model, search.from_year) == ("Toyota", "RAV4", 1997)
    assert search.transmission is None
    assert result.csv_import.unique_combos == 1


def test_a_utf8_byte_order_mark_does_not_hide_the_first_column(user):
    import_csv(make_csv("\ufeffMake,Model,Year\nCitroën,2CV,1970\n".encode()), user)

    search = CarSearch.objects.get()
    assert search.make == "Citroën"


def test_rejects_a_file_that_is_not_utf8(user):
    with pytest.raises(CsvImportError, match=r"UTF-8"):
        import_csv(make_csv("Make,Model,Year\nCitroën,2CV,1970\n".encode("cp1252")), user)


def test_cell_values_are_trimmed_before_dedupe(user):
    result = import_csv(make_csv("Make,Model,Year\nToyota,RAV4,1997\n  Toyota , RAV4 , 1997 \n"), user)

    assert result.csv_import.unique_combos == 1
    assert result.csv_import.duplicates_skipped == 1


def test_captures_transmission_from_first_occurrence(user):
    csv = make_csv("Make,Model,Year,Transmission\nToyota,RAV4,1997,Automatic 4-spd\nToyota,RAV4,1997,Manual 5-spd\n")

    import_csv(csv, user)

    assert CarSearch.objects.get().transmission == "Automatic 4-spd"


def test_a_blank_transmission_is_stored_as_null(user):
    import_csv(make_csv("Make,Model,Year,Transmission\nToyota,RAV4,1997,   \n"), user)

    assert CarSearch.objects.get().transmission is None


def test_rejects_when_projected_image_downloads_exceed_max(user, settings):
    settings.CARS_IMAGES = {
        **settings.CARS_IMAGES,
        "csv_import_default_images_per_year": 5,
        "csv_import_max_projected_images": 10,
    }

    with pytest.raises(CsvImportError) as excinfo:
        import_csv(make_csv(THREE_COMBOS), user)

    assert str(excinfo.value) == (
        "CSV produces 3 unique queries x 5 images = 15 image downloads, "
        "which exceeds the API download limit of 10. "
        "Split the CSV, or lower CSV_IMPORT_DEFAULT_IMAGES_PER_YEAR, and retry."
    )


def test_allows_import_when_projected_image_downloads_are_within_max(user, settings):
    settings.CARS_IMAGES = {
        **settings.CARS_IMAGES,
        "csv_import_default_images_per_year": 5,
        "csv_import_max_projected_images": 15,
    }

    result = import_csv(make_csv(THREE_COMBOS), user)

    assert result.csv_import.unique_combos == 3
    assert CarSearch.objects.count() == 3


def test_inserts_searches_in_batches_beyond_one_chunk(user, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "csv_import_max_projected_images": 10_000}
    rows = "".join(f"Toyota,Model {n},2000\n" for n in range(501))

    result = import_csv(make_csv("Make,Model,Year\n" + rows), user)

    assert result.csv_import.unique_combos == 501
    assert CarSearch.objects.filter(csv_import=result.csv_import).count() == 501


# --- Error log instrumentation (ErrorEventInstrumentationTest) ------------------


def test_a_rejected_csv_upload_is_logged_with_its_filename(user):
    with pytest.raises(CsvImportError):
        import_csv(make_csv("Colour,Size\nred,large\n", name="broken.csv"), user)

    event = ErrorEvent.objects.get(context=ErrorEvent.Context.CSV_UPLOAD)
    assert "Missing required columns" in event.message
    assert event.details == {"filename": "broken.csv"}
    assert event.csv_import_id is None
    assert event.exception_class == "CsvImportError"


def test_each_rejected_csv_row_is_logged_against_the_import(user):
    csv = make_csv(
        "Make,Model,Year\nToyota,Corolla,2019\nHonda,,2020\nFord,Focus,nineteen\nMazda,MX-5,1899\n",
        name="rows.csv",
    )

    result = import_csv(csv, user)

    assert result.skipped_invalid_rows == 3
    events = list(ErrorEvent.objects.filter(context=ErrorEvent.Context.CSV_ROW))
    assert len(events) == 3
    assert all(e.csv_import_id == result.csv_import.pk for e in events)
    assert all(e.severity == ErrorEvent.Severity.WARNING for e in events)

    by_row = {e.details["row_number"]: e for e in events}
    assert by_row[2].details["raw_row"] == "Honda,,2020"
    assert by_row[2].message == "Model missing."
    assert by_row[3].details["raw_row"] == "Ford,Focus,nineteen"
    assert by_row[3].message == "Year 'nineteen' is not a number."
    max_year = timezone.localdate().year + 1
    assert by_row[4].message == f"Year 1899 is outside the accepted range 1900-{max_year}."


def test_rejection_reasons_name_every_missing_field(user):
    import_csv(make_csv("Make,Model,Year\n,,\n\n"), user)

    messages = sorted(ErrorEvent.objects.values_list("message", flat=True))
    assert messages == ["Make, Model, Year missing.", "Make, Model, Year missing."]


def test_accepts_next_year_and_rejects_the_year_after(user):
    next_year = timezone.localdate().year + 1
    result = import_csv(make_csv(f"Make,Model,Year\nToyota,RAV4,{next_year}\nToyota,RAV4,{next_year + 1}\n"), user)

    assert result.csv_import.unique_combos == 1
    assert result.skipped_invalid_rows == 1


def test_non_ascii_digits_are_not_a_year(user):
    result = import_csv(make_csv("Make,Model,Year\nToyota,RAV4,١٩٩٧\n"), user)

    assert result.skipped_invalid_rows == 1
    assert ErrorEvent.objects.get().message == "Year '١٩٩٧' is not a number."


def test_duplicates_skipped_excludes_invalid_rows(user):
    csv = make_csv("Make,Model,Year\nToyota,RAV4,1997\nToyota,RAV4,1997\nToyota,,1997\nToyota,RAV4,abc\n")

    result = import_csv(csv, user)

    assert result.csv_import.total_rows == 4
    assert result.csv_import.unique_combos == 1
    assert result.csv_import.duplicates_skipped == 1
    assert result.skipped_invalid_rows == 2
