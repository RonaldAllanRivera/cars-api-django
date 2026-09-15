import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts import abilities
from apps.imports.models import CsvImport
from apps.searches.models import CarSearch
from tests.api.helpers import error_fields
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def csv_upload(content: str, name: str = "queries.csv", content_type: str = "text/csv") -> dict:
    return {"csv_file": SimpleUploadedFile(name, content.encode(), content_type=content_type)}


def test_it_lists_imports_newest_first(client, acting_as, make_import):
    acting_as()
    older = make_import(original_filename="older.csv")
    newer = make_import(original_filename="newer.csv")

    data = client.get("/api/v1/imports").json()["data"]

    assert [row["id"] for row in data] == [newer.id, older.id]


def test_it_names_the_importer_without_leaking_their_email(client, acting_as, make_import):
    acting_as()
    make_import(UserFactory(name="Allan", email="allan@example.com"))

    response = client.get("/api/v1/imports")

    assert response.json()["data"][0]["importer_name"] == "Allan"
    assert b"allan@example.com" not in response.content


def test_the_list_carries_no_coverage(client, acting_as, make_import):
    acting_as()
    make_import()

    row = client.get("/api/v1/imports").json()["data"][0]

    assert "coverage" not in row
    assert list(row) == [
        "id",
        "original_filename",
        "total_rows",
        "unique_combos",
        "duplicates_skipped",
        "imported_by",
        "importer_name",
        "searches_count",
        "created_at",
    ]


def test_the_detail_carries_coverage(client, acting_as, make_import, make_search, make_image):
    user = acting_as()
    csv_import = make_import()
    make_image(make_search(user, csv_import=csv_import, status=CarSearch.Status.COMPLETED))
    make_search(user, csv_import=csv_import, status=CarSearch.Status.PENDING)

    coverage = client.get(f"/api/v1/imports/{csv_import.id}").json()["data"]["coverage"]

    assert coverage == {"total": 2, "searched": 1, "not_run": 1, "failed": 0, "with_images": 1, "no_images": 0}


def test_coverage_is_null_for_an_import_with_no_searches(client, acting_as, make_import):
    acting_as()
    csv_import = make_import()

    data = client.get(f"/api/v1/imports/{csv_import.id}").json()["data"]

    assert "coverage" in data
    assert data["coverage"] is None


def test_an_unknown_import_404s(client, acting_as):
    acting_as()

    assert client.get("/api/v1/imports/999999").status_code == 404


def test_it_counts_the_import_searches(client, acting_as, make_import, make_search):
    user = acting_as()
    csv_import = make_import()
    for _ in range(3):
        make_search(user, csv_import=csv_import)

    assert client.get("/api/v1/imports").json()["data"][0]["searches_count"] == 3


def test_the_list_runs_a_constant_number_of_queries(client, acting_as, make_import, django_assert_max_num_queries):
    acting_as([abilities.IMPORTS_READ])
    for _ in range(3):
        make_import()

    with django_assert_max_num_queries(3):
        assert client.get("/api/v1/imports").status_code == 200


def test_reading_imports_requires_the_imports_read_ability(client, acting_as, make_import):
    acting_as([abilities.SEARCH_READ])
    make_import()

    assert client.get("/api/v1/imports").status_code == 403


def test_imports_require_authentication(client):
    assert client.get("/api/v1/imports").status_code == 401


def test_it_imports_an_uploaded_csv(client, acting_as):
    acting_as()

    response = client.post(
        "/api/v1/imports", csv_upload("Make,Model,Year\nToyota,Corolla,1998\nHonda,Civic,1999\n"), format="multipart"
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["original_filename"] == "queries.csv"
    assert data["unique_combos"] == 2
    assert data["searches_count"] == 2
    assert data["coverage"]["not_run"] == 2
    assert CarSearch.objects.filter(csv_import__isnull=False).count() == 2


def test_it_records_who_uploaded(client, acting_as):
    user = acting_as()

    client.post("/api/v1/imports", csv_upload("Make,Model,Year\nKia,Rio,2010\n", "q.csv"), format="multipart")

    assert CsvImport.objects.get().imported_by == user


def test_the_content_type_is_sniffed_not_trusted(client, acting_as):
    acting_as()

    response = client.post(
        "/api/v1/imports",
        csv_upload("Make,Model,Year\nKia,Rio,2010\n", "q.csv", content_type="application/octet-stream"),
        format="multipart",
    )

    assert response.status_code == 201


def test_a_binary_upload_is_rejected(client, acting_as):
    acting_as()
    upload = {"csv_file": SimpleUploadedFile("q.csv", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="text/csv")}

    assert error_fields(client.post("/api/v1/imports", upload, format="multipart")) == {"csv_file"}


def test_an_oversized_upload_is_rejected(client, acting_as, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "csv_import_max_upload_kb": 1}
    acting_as()
    content = "Make,Model,Year\n" + "Toyota,Corolla,1998\n" * 100

    assert error_fields(client.post("/api/v1/imports", csv_upload(content), format="multipart")) == {"csv_file"}
    assert not CsvImport.objects.exists()


def test_it_rejects_a_csv_missing_required_columns(client, acting_as):
    acting_as()

    response = client.post("/api/v1/imports", csv_upload("Make,Year\nToyota,1998\n", "bad.csv"), format="multipart")

    assert error_fields(response) == {"csv_file"}
    assert not CsvImport.objects.exists()


def test_it_requires_a_file(client, acting_as):
    acting_as()

    assert error_fields(client.post("/api/v1/imports", {}, format="multipart")) == {"csv_file"}


def test_uploading_requires_the_imports_write_ability(client, acting_as):
    acting_as([abilities.IMPORTS_READ])

    response = client.post("/api/v1/imports", csv_upload("Make,Model,Year\nKia,Rio,2010\n"), format="multipart")

    assert response.status_code == 403
    assert not CsvImport.objects.exists()
