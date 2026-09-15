import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from api.authentication import BearerTokenAuthentication
from apps.accounts import abilities
from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from tests.factories import CsvImportFactory, issue_token

pytestmark = pytest.mark.django_db


def test_abilities_intersect_in_canonical_order():
    assert abilities.resolve(["exports:read", "search:read", "bogus"]) == ["search:read", "exports:read"]
    assert abilities.resolve(None) == abilities.DEFAULT


def test_bearer_token_round_trip_and_hash_at_rest():
    user, plain = issue_token()
    token = user.api_tokens.get()
    assert plain.split("|", 1)[1] not in token.token_hash
    assert token.can("search:read")


def test_invalid_bearer_token_is_rejected():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer 1|nope")
    with pytest.raises(AuthenticationFailed):
        BearerTokenAuthentication().authenticate(request)


def test_error_logger_clamps_and_never_raises():
    try:
        raise RuntimeError("é" * 3000)
    except RuntimeError as exc:
        event = error_logger.record("search_run", exc, details={"excerpt": "x" * 5000})
    assert event is not None
    assert len(event.exception_message.encode()) <= 2000
    assert len(event.details["excerpt"]) == 1000
    assert event.trace_excerpt


def test_error_logger_caps_events_per_import(settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "error_log_max_events_per_import": 2}
    csv_import = CsvImportFactory()
    for _ in range(5):
        error_logger.record("csv_row", "bad row", csv_import=csv_import, severity="warning")
    events = ErrorEvent.objects.filter(csv_import=csv_import).order_by("id")
    assert events.count() == 3
    assert "suppressed after 2 events" in events.last().message
