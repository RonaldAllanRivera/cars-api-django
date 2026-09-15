import pytest
from django.db import DatabaseError

from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from tests.factories import CarSearchFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


def raised(error: BaseException) -> BaseException:
    try:
        raise error
    except BaseException as caught:
        return caught


def nested_failure(depth: int) -> None:
    if depth <= 0:
        raise RuntimeError("deep")
    _nested_failure_again(depth - 1)


def _nested_failure_again(depth: int) -> None:
    # Alternating frames: the traceback module collapses identical consecutive ones.
    nested_failure(depth)


def cap_events_per_import(settings, cap: int) -> None:
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "error_log_max_events_per_import": cap}


def test_records_an_exception_with_its_class_message_and_trace():
    error_logger.record("search_run", raised(RuntimeError("Wikimedia returned nothing")))

    event = ErrorEvent.objects.get()
    assert event.context == "search_run"
    assert event.severity == "error"
    assert event.message == "Wikimedia returned nothing"
    assert event.exception_class == "RuntimeError"
    assert event.exception_message == "Wikimedia returned nothing"
    assert "test_error_logger" in event.trace_excerpt
    assert event.occurred_at is not None


def test_records_a_plain_string_problem_without_exception_columns():
    error_logger.record("csv_row", "Year 1899 is out of range")

    event = ErrorEvent.objects.get()
    assert event.message == "Year 1899 is out of range"
    assert event.exception_class is None
    assert event.exception_message is None
    assert event.trace_excerpt is None
    assert event.details is None


def test_an_explicit_message_overrides_the_exception_text():
    error_logger.record("search_run", raised(ValueError("low level")), message="Search for Toyota failed")

    event = ErrorEvent.objects.get()
    assert event.message == "Search for Toyota failed"
    assert event.exception_message == "low level"


def test_stores_links_and_details():
    csv_import = CsvImportFactory()
    search = CarSearchFactory(csv_import=csv_import)

    error_logger.record(
        "image_download",
        "Fetch failed",
        car_search=search,
        csv_import=csv_import.pk,
        details={"http_status": 404, "url": "https://upload.wikimedia.org/a.jpg"},
    )

    event = ErrorEvent.objects.get()
    assert event.car_search_id == search.pk
    assert event.csv_import_id == csv_import.pk
    assert event.details == {"http_status": 404, "url": "https://upload.wikimedia.org/a.jpg"}


def test_truncates_an_oversized_exception_message():
    error_logger.record("search_run", raised(RuntimeError("x" * 5000)))

    event = ErrorEvent.objects.get()
    assert len(event.exception_message) == error_logger.EXCEPTION_MESSAGE_BYTES
    assert len(event.message) == error_logger.MESSAGE_BYTES


def test_truncates_an_oversized_detail_value():
    error_logger.record("search_run", "Blocked", details={"response_excerpt": "y" * 5000})

    assert len(ErrorEvent.objects.get().details["response_excerpt"]) == error_logger.DETAIL_STRING_BYTES


def test_truncation_never_splits_a_multibyte_character():
    error_logger.record("search_run", "é" * 400)

    message = ErrorEvent.objects.get().message
    assert len(message.encode()) == error_logger.MESSAGE_BYTES
    assert set(message) == {"é"}


def test_keeps_only_the_frames_nearest_the_raise():
    try:
        nested_failure(40)
    except RuntimeError as exc:
        error_logger.record("search_run", exc)

    trace = ErrorEvent.objects.get().trace_excerpt
    assert trace.count('  File "') == error_logger.TRACE_FRAMES
    assert "raise RuntimeError" in trace.splitlines()[-1]


def test_a_failing_write_does_not_propagate_to_the_caller(monkeypatch):
    def broken_create(**kwargs):
        raise DatabaseError('relation "observability_errorevent" does not exist')

    monkeypatch.setattr(ErrorEvent.objects, "create", broken_create)

    assert error_logger.record("search_run", raised(RuntimeError("the original failure"))) is None


def test_undecodable_detail_values_are_stored_rather_than_breaking_the_write():
    # Bytes decoded with surrogateescape: Python's equivalent of invalid UTF-8.
    excerpt = b"\xc3\x28 binary \xff\xfe".decode("utf-8", errors="surrogateescape")

    error_logger.record("image_download", "Fetch failed", details={"response_excerpt": excerpt})

    assert "binary" in ErrorEvent.objects.get().details["response_excerpt"]


def test_nul_characters_are_scrubbed_because_postgres_rejects_them():
    # A binary response body decodes to text containing NULs, which neither a
    # PostgreSQL text column nor jsonb will accept.
    excerpt = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR".decode("utf-8", errors="replace")

    event = error_logger.record(
        "image_download", "Fetch\x00 failed", details={"response_excerpt": excerpt, "nested": ["a\x00b"]}
    )

    assert event is not None
    event.refresh_from_db()
    assert event.message == "Fetch failed"
    assert "IHDR" in event.details["response_excerpt"]
    assert "\x00" not in event.details["response_excerpt"]
    assert event.details["nested"] == ["ab"]


def test_caps_the_events_stored_for_one_import_and_says_so_once(settings):
    cap_events_per_import(settings, 3)
    csv_import = CsvImportFactory()

    for i in range(1, 11):
        error_logger.record("csv_row", f"Row {i} rejected", csv_import=csv_import)

    events = list(ErrorEvent.objects.filter(csv_import=csv_import).order_by("id"))
    assert len(events) == 4
    assert [e.severity for e in events].count("warning") == 1
    assert events[-1].message == "Further errors for this import were suppressed after 3 events."


def test_the_cap_is_recounted_from_the_database_not_from_process_state(settings):
    cap_events_per_import(settings, 2)
    csv_import = CsvImportFactory()

    for message in ("first", "second", "third", "fourth"):
        error_logger.record("csv_row", message, csv_import=csv_import.pk)

    assert ErrorEvent.objects.filter(csv_import=csv_import).count() == 3


def test_a_cap_of_zero_disables_the_cap(settings):
    cap_events_per_import(settings, 0)
    csv_import = CsvImportFactory()

    for i in range(3):
        error_logger.record("csv_row", f"Row {i} rejected", csv_import=csv_import)

    assert ErrorEvent.objects.filter(csv_import=csv_import, severity="error").count() == 3


def test_events_without_an_import_are_not_capped(settings):
    cap_events_per_import(settings, 2)

    for i in range(1, 6):
        error_logger.record("search_run", f"failure {i}")

    assert ErrorEvent.objects.count() == 5


def test_an_error_event_survives_deletion_of_the_import_it_describes():
    csv_import = CsvImportFactory()
    error_logger.record("csv_upload", "Missing required columns", csv_import=csv_import)

    csv_import.delete()

    event = ErrorEvent.objects.get()
    assert event.csv_import_id is None
    assert event.message == "Missing required columns"
