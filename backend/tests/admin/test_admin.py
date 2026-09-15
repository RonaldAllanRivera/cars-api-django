from datetime import timedelta
from unittest import mock

import pytest
from django.contrib import admin
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import ApiToken, User
from apps.catalog.models import CarMake
from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch, CommonsCategoryLookup, WikimediaBlockEvent
from apps.searches.services.wikimedia import WikimediaBlockedError
from tests.factories import (
    CarImageFactory,
    CarModelFactory,
    CarSearchFactory,
    CsvImportFactory,
    ErrorEventFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

PROJECT_APPS = ("accounts", "catalog", "imports", "searches", "images", "observability")


@pytest.fixture
def superuser():
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def admin_client(client, superuser):
    client.force_login(superuser)
    return client


@pytest.fixture
def records(superuser):
    """One saved row for every model the admin exposes."""
    csv_import = CsvImportFactory(imported_by=superuser)
    search = CarSearchFactory(csv_import=csv_import, status=CarSearch.Status.COMPLETED, commons_category="Toyota RAV4")
    image = CarImageFactory(car_search=search, thumbnail_url="https://upload.wikimedia.org/thumb.jpg")
    token, _ = ApiToken.issue(superuser, "mobile", ["search:read"])
    return {
        User: superuser,
        ApiToken: token,
        CarMake: CarModelFactory().make,
        csv_import._meta.model: csv_import,
        CarSearch: search,
        CarImage: image,
        CommonsCategoryLookup: CommonsCategoryLookup.objects.create(make="Toyota", model="RAV4", category=None),
        WikimediaBlockEvent: WikimediaBlockEvent.objects.create(
            car_search=search, csv_import=csv_import, status_code=429, retry_after_seconds=60
        ),
        ErrorEvent: ErrorEventFactory(
            car_search=search, csv_import=csv_import, details={"status": 502, "query": "Toyota RAV4"}
        ),
    }


def registered_models():
    return [model for model in admin.site._registry if model._meta.app_label in PROJECT_APPS]


def url(model, view, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{view}", args=args)


def changelist_action(client, model, action, objects, **extra):
    data = {"action": action, "_selected_action": [obj.pk for obj in objects], **extra}
    return client.post(url(model, "changelist"), data)


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


# ---------------------------------------------------------------------------
# Every page renders
# ---------------------------------------------------------------------------


def test_every_project_model_is_registered():
    names = {model.__name__ for model in registered_models()}
    assert names == {
        "User",
        "ApiToken",
        "CarMake",
        "CsvImport",
        "CarSearch",
        "CarImage",
        "CommonsCategoryLookup",
        "WikimediaBlockEvent",
        "ErrorEvent",
    }


@pytest.mark.parametrize("model", registered_models(), ids=lambda m: m.__name__)
def test_changelist_add_and_change_pages_render(admin_client, records, model):
    model_admin = admin.site._registry[model]

    assert admin_client.get(url(model, "changelist")).status_code == 200
    assert admin_client.get(url(model, "changelist"), {"q": "toyota"}).status_code == 200

    add = admin_client.get(url(model, "add"))
    assert add.status_code == (200 if model_admin.has_add_permission(add.wsgi_request) else 403)

    assert admin_client.get(url(model, "change", records[model].pk)).status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {"source": "csv"},
        {"source": "adhoc"},
        {"coverage": "with_images"},
        {"coverage": "no_images"},
        {"coverage": "not_run"},
        {"status__exact": "completed"},
    ],
)
def test_search_filters_render(admin_client, records, params):
    response = admin_client.get(url(CarSearch, "changelist"), params)
    assert response.status_code == 200


def test_search_coverage_filter_separates_empty_runs(admin_client, records):
    empty = CarSearchFactory(status=CarSearch.Status.COMPLETED, make="Lada")
    response = admin_client.get(url(CarSearch, "changelist"), {"coverage": "no_images"})
    shown = list(response.context["cl"].result_list)
    assert shown == [empty]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


def test_add_user_with_password(admin_client):
    response = admin_client.post(
        url(User, "add"),
        {
            "email": "reviewer@example.test",
            "name": "Reviewer",
            "usable_password": "true",
            "password1": "a-long-unusual-passphrase",
            "password2": "a-long-unusual-passphrase",
            "is_staff": "on",
            "is_active": "on",
        },
    )
    assert response.status_code == 302, response.context["adminform"].form.errors
    user = User.objects.get(email="reviewer@example.test")
    assert user.is_staff and user.check_password("a-long-unusual-passphrase")


def test_add_user_rejects_duplicate_email_case_insensitively(admin_client, superuser):
    response = admin_client.post(
        url(User, "add"),
        {
            "email": superuser.email.upper(),
            "name": "Dup",
            "usable_password": "true",
            "password1": "a-long-unusual-passphrase",
            "password2": "a-long-unusual-passphrase",
        },
    )
    assert response.status_code == 200
    assert "email" in response.context["adminform"].form.errors


def test_token_pages_never_show_the_hash(admin_client, records):
    token = records[ApiToken]
    for page in (url(ApiToken, "changelist"), url(ApiToken, "change", token.pk), url(User, "change", token.user_id)):
        assert token.token_hash not in admin_client.get(page).content.decode()


def test_revoke_selected_tokens(admin_client, records):
    token = records[ApiToken]
    response = changelist_action(admin_client, ApiToken, "revoke_selected", [token])
    assert response.status_code == 302
    assert not ApiToken.objects.filter(pk=token.pk).exists()
    assert "Revoked 1 token." in message_texts(response)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def test_create_make_with_inline_models(admin_client):
    response = admin_client.post(
        url(CarMake, "add"),
        {
            "name": "Subaru",
            "models-TOTAL_FORMS": "2",
            "models-INITIAL_FORMS": "0",
            "models-0-name": "Outback",
            "models-1-name": "Forester",
        },
    )
    assert response.status_code == 302
    assert sorted(CarMake.objects.get(name="Subaru").models.values_list("name", flat=True)) == ["Forester", "Outback"]


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------


def test_import_page_shows_coverage(admin_client, records):
    csv_import = records[CarSearch].csv_import
    CarSearchFactory(csv_import=csv_import, status=CarSearch.Status.PENDING)
    content = admin_client.get(url(csv_import._meta.model, "change", csv_import.pk)).content.decode()
    assert "Not run" in content and "With images" in content
    assert "coverage=not_run" in content


def test_deleting_an_import_removes_its_searches_and_images(admin_client, records):
    search = records[CarSearch]
    csv_import = search.csv_import
    response = admin_client.post(url(csv_import._meta.model, "delete", csv_import.pk), {"post": "yes"})
    assert response.status_code == 302
    assert not CarSearch.objects.filter(pk=search.pk).exists()
    assert not CarImage.objects.filter(pk=records[CarImage].pk).exists()


# ---------------------------------------------------------------------------
# Searches
# ---------------------------------------------------------------------------


def test_run_selected_calls_the_service_for_each_search(admin_client):
    searches = CarSearchFactory.create_batch(2)

    def complete(search):
        search.status = CarSearch.Status.COMPLETED
        return search

    with mock.patch("apps.searches.services.run_query.run_search_query", side_effect=complete) as run:
        response = changelist_action(admin_client, CarSearch, "run_selected", searches)

    assert response.status_code == 302
    assert [call.args[0].pk for call in run.call_args_list] == sorted(s.pk for s in searches)
    assert "Ran 2 searches: 2 completed, 0 failed." in message_texts(response)


def test_run_selected_stops_when_wikimedia_blocks(admin_client):
    searches = CarSearchFactory.create_batch(3)
    blocked = WikimediaBlockedError(429, retry_after_seconds=120)

    with mock.patch("apps.searches.services.run_query.run_search_query", side_effect=[searches[0], blocked]) as run:
        response = changelist_action(admin_client, CarSearch, "run_selected", searches)

    assert run.call_count == 2
    [message] = message_texts(response)
    assert "HTTP 429" in message and "2 not run" in message and "Retry after 120s" in message


def test_run_selected_counts_failures_and_continues(admin_client):
    searches = CarSearchFactory.create_batch(2)
    with mock.patch(
        "apps.searches.services.run_query.run_search_query", side_effect=[RuntimeError("boom"), searches[1]]
    ) as run:
        response = changelist_action(admin_client, CarSearch, "run_selected", searches)

    assert run.call_count == 2
    assert "Ran 2 searches: 1 completed, 1 failed." in message_texts(response)


def test_refresh_selected_calls_refresh_search(admin_client):
    search = CarSearchFactory()
    with mock.patch("apps.searches.services.search_service.refresh_search", return_value=search) as refresh:
        changelist_action(admin_client, CarSearch, "refresh_selected", [search])
    refresh.assert_called_once()


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "status"),
    [("approve_selected", "approved"), ("reject_selected", "rejected")],
)
def test_review_actions_record_the_reviewer(admin_client, superuser, action, status):
    images = CarImageFactory.create_batch(2)
    changelist_action(admin_client, CarImage, action, images)
    for image in images:
        image.refresh_from_db()
        assert image.review_status == status
        assert image.reviewed_by == superuser
        assert image.reviewed_at is not None


def test_reset_to_pending_clears_the_reviewer(admin_client, superuser):
    image = CarImageFactory(review_status="approved", reviewed_by=superuser, reviewed_at=timezone.now())
    changelist_action(admin_client, CarImage, "reset_selected", [image])
    image.refresh_from_db()
    assert (image.review_status, image.reviewed_by, image.reviewed_at) == ("pending", None, None)


def test_changing_review_status_on_the_detail_page_stamps_the_reviewer(admin_client, superuser):
    image = CarImageFactory()
    response = admin_client.post(url(CarImage, "change", image.pk), {"review_status": "approved"})
    assert response.status_code == 302
    image.refresh_from_db()
    assert image.review_status == "approved" and image.reviewed_by == superuser


def test_download_selected_as_zip(admin_client):
    images = CarImageFactory.create_batch(2)

    def build(queryset, path):
        with open(path, "wb") as fh:
            fh.write(b"PK-fake-zip")
        return len(list(queryset))

    with mock.patch("apps.exports.services.zip_builder.build_zip_to_file", side_effect=build):
        response = changelist_action(admin_client, CarImage, "download_zip", images)

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="car-images-')
    assert b"".join(response.streaming_content) == b"PK-fake-zip"


def test_zip_respects_the_image_cap(admin_client, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "bulk_download_max_images": 1}
    images = CarImageFactory.create_batch(2)
    with mock.patch("apps.exports.services.zip_builder.build_zip_to_file") as build:
        response = changelist_action(admin_client, CarImage, "download_zip", images)
    build.assert_not_called()
    assert response.status_code == 302
    assert any("at most 1" in m for m in message_texts(response))


def test_zip_with_no_downloadable_images_is_reported_not_served(admin_client):
    image = CarImageFactory()
    with mock.patch("apps.exports.services.zip_builder.build_zip_to_file", return_value=0):
        response = changelist_action(admin_client, CarImage, "download_zip", [image])
    assert response.status_code == 302
    assert any("None of the selected images" in m for m in message_texts(response))


def test_export_selected_as_csv(admin_client):
    image = CarImageFactory()
    rows = [["Year", "Make"], ["1997", "Toyota"]]
    with mock.patch("apps.exports.services.csv_exporter.export_rows", return_value=iter(rows)) as export:
        response = changelist_action(admin_client, CarImage, "export_csv", [image])
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert b"".join(response.streaming_content).decode().splitlines() == ["Year,Make", "1997,Toyota"]
    assert [i.pk for i in export.call_args.args[0]] == [image.pk]


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


def test_error_event_detail_pretty_prints_details(admin_client, records):
    event = records[ErrorEvent]
    content = admin_client.get(url(ErrorEvent, "change", event.pk)).content.decode()
    assert "&quot;query&quot;: &quot;Toyota RAV4&quot;" in content


def test_prune_old_error_events(admin_client, settings):
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "error_log_retention_days": 30}
    old = ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=31))
    recent = ErrorEventFactory()

    changelist = admin_client.get(url(ErrorEvent, "changelist")).content.decode()
    assert url(ErrorEvent, "prune") in changelist

    confirm = admin_client.get(url(ErrorEvent, "prune"))
    assert confirm.status_code == 200 and confirm.context["prunable"] == 1

    response = admin_client.post(url(ErrorEvent, "prune"))
    assert response.status_code == 302
    assert list(ErrorEvent.objects.all()) == [recent]
    assert not ErrorEvent.objects.filter(pk=old.pk).exists()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_anonymous_and_non_staff_users_are_sent_to_login(client):
    for user in (None, UserFactory(is_staff=False)):
        if user:
            client.force_login(user)
        for page in (reverse("admin:index"), url(CarImage, "changelist"), url(ErrorEvent, "prune")):
            response = client.get(page)
            assert response.status_code == 302
            assert response["Location"].startswith(reverse("admin:login"))


def test_staff_without_permissions_is_forbidden(client):
    client.force_login(UserFactory(is_staff=True))
    assert client.get(url(CarImage, "changelist")).status_code == 403
    assert client.get(url(ErrorEvent, "prune")).status_code == 403
    image = CarImageFactory()
    response = changelist_action(client, CarImage, "approve_selected", [image])
    assert response.status_code == 403
    image.refresh_from_db()
    assert image.review_status == "pending"
