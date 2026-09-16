"""
The mobile client's contract, pinned by the fixtures its Zod schemas are
tested against (mobile/src/api/__fixtures__). This builds the same data,
calls the real endpoints and asserts every response still matches - values,
keys and key order.

A failure here means the API shape drifted from what the deployed app parses.
"""

import json
from pathlib import Path

import httpx
import pytest
from django.conf import settings

from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch
from tests.factories import UserFactory, issue_token

FIXTURE_DIR = Path(settings.BASE_DIR).parent / "mobile" / "src" / "api" / "__fixtures__"
TOKEN_PLACEHOLDER = "1|fixture-token-not-a-real-credential"


def commons_response(request: httpx.Request) -> httpx.Response:
    """
    The two Commons calls a fresh search makes: the category probe (any
    `titles` resolves) and the file listing (one file naming the search year).
    """
    titles = request.url.params.get("titles")
    if titles is not None:
        page = {"title": titles, "pageid": 1, "categoryinfo": {"files": 1, "subcats": 0}}
        return httpx.Response(200, json={"query": {"pages": [page]}})

    image_info = {
        "url": "https://upload.wikimedia.org/fixture-create.jpg",
        "thumburl": "https://upload.wikimedia.org/thumb/fixture-create.jpg",
        "width": 1024,
        "height": 768,
        "mime": "image/jpeg",
        "extmetadata": {
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "Artist": {"value": "Fixture Photographer"},
            "ImageDescription": {"value": "A 1997 Honda CR-V, photographed for the fixtures."},
        },
    }
    page = {"pageid": 501, "title": "File:1997 Honda CR-V LX.jpg", "imageinfo": [image_info]}
    return httpx.Response(200, json={"query": {"pages": [page]}})


def build_data():
    user = UserFactory(name="Fixture User", email="fixtures@example.test")

    # An import with one run search and one unrun, so coverage pins real counts.
    csv_import = CsvImport.objects.create(
        original_filename="queries.csv", total_rows=2, unique_combos=2, imported_by=user
    )
    search_fields = {"from_year": 1997, "to_year": 1997, "images_per_year": 5, "requested_by": user}
    search = CarSearch.objects.create(
        make="Toyota", model="RAV4", status=CarSearch.Status.COMPLETED, csv_import=csv_import, **search_fields
    )
    CarSearch.objects.create(
        make="Honda", model="Civic", status=CarSearch.Status.PENDING, csv_import=csv_import, **search_fields
    )

    image_fields = {"car_search": search, "make": "Toyota", "model": "RAV4", "year": 1997, "provider": "wikimedia"}
    reviewed = CarImage.objects.create(
        **image_fields,
        provider_image_id="fixture-a",
        title="File:Toyota RAV4 1997 front.jpg",
        source_url="https://upload.wikimedia.org/fixture-a.jpg",
        thumbnail_url="https://upload.wikimedia.org/thumb/fixture-a.jpg",
        width=800,
        height=600,
        description="A first-generation RAV4, photographed from the front.",
        color="silver",
        license="CC BY-SA 4.0",
        attribution="Photo by A. Person, CC BY-SA 4.0",
        make_confirmed=True,
        year_confirmed=False,
        review_status=CarImage.ReviewStatus.APPROVED,
        reviewed_by=user,
        reviewed_at="2026-01-15T09:00:00Z",
        download_status=CarImage.DownloadStatus.DOWNLOADED,
    )
    pending = CarImage.objects.create(
        **image_fields,
        provider_image_id="fixture-b",
        title="File:Toyota RAV4 1997 rear.jpg",
        source_url="https://upload.wikimedia.org/fixture-b.jpg",
    )

    ErrorEvent.objects.create(
        context=ErrorEvent.Context.SEARCH_RUN,
        severity=ErrorEvent.Severity.ERROR,
        message="The search run failed.",
        exception_class="RuntimeError",
        exception_message="Connection timed out",
        trace_excerpt=(
            '  File "/app/apps/searches/services/run_query.py", line 48, in run_search_query\n    run_search(search)'
        ),
        details={"attempt": 2},
        car_search=search,
    )
    return user, csv_import, search, reviewed, pending


@pytest.fixture
def responses(client, respx_mock, time_machine) -> dict[str, object]:
    # Frozen so every timestamp is stable; sequences are reset so every id is.
    time_machine.move_to("2026-01-15T09:00:00Z", tick=False)
    respx_mock.get(url__startswith=settings.WIKIMEDIA["base_url"]).mock(side_effect=commons_response)
    user, csv_import, search, reviewed, pending = build_data()

    def call(method: str, path: str, expected: int, body: dict | None = None) -> object:
        response = getattr(client, method)(path, body, format="json", SERVER_NAME="localhost")
        assert response.status_code == expected, (path, response.content)
        return response.json()

    login = call(
        "post",
        "/api/v1/auth/login",
        201,
        {"email": "fixtures@example.test", "password": "password", "device_name": "fixture-device"},
    )
    login["token"] = TOKEN_PLACEHOLDER

    _, plain = issue_token(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {plain}")

    return {
        "login": login,
        "me": call("get", "/api/v1/auth/me", 200),
        "image": call("get", f"/api/v1/images/{reviewed.id}", 200),
        "images": call("get", "/api/v1/images?per_page=1", 200),
        "search": call("get", f"/api/v1/searches/{search.id}", 200),
        "searches": call("get", "/api/v1/searches", 200),
        "imports": call("get", "/api/v1/imports?per_page=1", 200),
        "import": call("get", f"/api/v1/imports/{csv_import.id}", 200),
        "errors": call("get", "/api/v1/errors", 200),
        "health": call("get", "/api/v1/health/summary", 200),
        "validation-error": call(
            "post", "/api/v1/searches", 422, {"make": "Toyota", "from_year": 1990, "to_year": 2020}
        ),
        "review": call("patch", f"/api/v1/images/{pending.id}/review", 200, {"review_status": "rejected"}),
        # The one response that embeds a populated `images` array.
        "search-create": call(
            "post",
            "/api/v1/searches",
            201,
            {"make": "Honda", "model": "CR-V", "from_year": 1997, "to_year": 1997, "images_per_year": 2},
        ),
    }


@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_the_live_api_matches_every_committed_fixture(responses):
    fixtures = sorted(path.stem for path in FIXTURE_DIR.glob("*.json"))
    assert fixtures == sorted(responses), "a fixture exists with no endpoint call here, or the reverse"

    for name, payload in responses.items():
        committed = (FIXTURE_DIR / f"{name}.json").read_text()
        assert payload == json.loads(committed), f"{name}.json no longer matches the API response"
        # Byte-for-byte against the committed fixture, which also pins key order.
        assert json.dumps(payload, indent=4, ensure_ascii=False) + "\n" == committed, f"{name}.json key order"
