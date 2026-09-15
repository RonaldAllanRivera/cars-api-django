import uuid
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.models import User
from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.searches.models import CarSearch
from tests.factories import UserFactory, issue_token


@pytest.fixture
def client() -> APIClient:
    """An unauthenticated API client (overrides pytest-django's plain client)."""
    return APIClient()


@pytest.fixture
def acting_as(client: APIClient) -> Callable[..., User]:
    """
    Authenticate `client` with a real bearer token for a new (or given) user.
    Defaults to every ability, so a test expecting a 403 narrows it on purpose.
    """

    def authenticate(token_abilities: list[str] | None = None, user: User | None = None) -> User:
        user, plain = issue_token(user, token_abilities)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plain}")
        return user

    return authenticate


@pytest.fixture
def throttle_rate(settings, monkeypatch) -> Callable[[str, str], None]:
    """
    Set one scope's production-like rate. DRF binds THROTTLE_RATES when the
    throttling module is first imported, so a settings override alone does not
    reach it; the bound dict is patched too.
    """

    def set_rate(scope: str, rate: str) -> None:
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {**rates, scope: rate}}
        monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, scope, rate)

    return set_rate


@pytest.fixture
def make_search() -> Callable[..., CarSearch]:
    def create(user: User | None = None, **overrides) -> CarSearch:
        fields = {
            "make": "Toyota",
            "model": "RAV4",
            "from_year": 1997,
            "to_year": 1997,
            "transparent_background": False,
            "images_per_year": 5,
            "status": CarSearch.Status.COMPLETED,
            "requested_by": user or UserFactory(),
        }
        return CarSearch.objects.create(**(fields | overrides))

    return create


@pytest.fixture
def make_import() -> Callable[..., CsvImport]:
    def create(importer: User | None = None, **overrides) -> CsvImport:
        fields = {
            "original_filename": "queries.csv",
            "total_rows": 0,
            "unique_combos": 0,
            "duplicates_skipped": 0,
            "imported_by": importer or UserFactory(),
        }
        return CsvImport.objects.create(**(fields | overrides))

    return create


@pytest.fixture
def make_image() -> Callable[..., CarImage]:
    def create(search: CarSearch, **overrides) -> CarImage:
        key = f"img-{uuid.uuid4().hex}"
        fields = {
            "car_search": search,
            "provider": "wikimedia",
            "provider_image_id": key,
            "make": search.make,
            "model": search.model,
            "year": search.from_year,
            "title": f"File:{search.make} {key}.jpg",
            "source_url": f"https://upload.wikimedia.org/{key}.jpg",
            "thumbnail_url": f"https://upload.wikimedia.org/thumb/{key}.jpg",
            "width": 800,
            "height": 600,
            "download_status": CarImage.DownloadStatus.NOT_DOWNLOADED,
        }
        return CarImage.objects.create(**(fields | overrides))

    return create
