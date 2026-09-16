from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.observability.services import dashboard
from apps.searches.models import CarSearch
from tests.factories import (
    CarImageFactory,
    CarSearchFactory,
    CsvImportFactory,
    ErrorEventFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    user = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(user)
    return client


def stat(metrics, label):
    return next(entry for entry in metrics["stats"] if entry.label == label)


class TestStats:
    def test_windows_exclude_older_rows(self):
        now = timezone.now()
        ErrorEventFactory(occurred_at=now - timedelta(hours=2))
        ErrorEventFactory(occurred_at=now - timedelta(days=3))
        CarSearchFactory(status=CarSearch.Status.FAILED)
        old_search = CarSearchFactory(status=CarSearch.Status.FAILED)
        CarSearch.objects.filter(pk=old_search.pk).update(created_at=now - timedelta(days=9))
        CarImageFactory()
        old_image = CarImageFactory()
        CarImage.objects.filter(pk=old_image.pk).update(created_at=now - timedelta(days=8))

        metrics = dashboard.dashboard_metrics()

        assert stat(metrics, "Errors (24h)").value == 1, "Only the last 24 hours count."
        assert stat(metrics, "Failed searches (7d)").value == 1
        assert stat(metrics, "Images collected (7d)").value == 1

    def test_quiet_pipeline_reads_as_good(self):
        metrics = dashboard.dashboard_metrics()
        errors = stat(metrics, "Errors (24h)")
        assert (errors.value, errors.tone, errors.description) == (0, "good", "Pipeline is quiet")

    def test_errors_turn_the_stat_bad_and_link_to_the_log(self):
        ErrorEventFactory()
        errors = stat(dashboard.dashboard_metrics(), "Errors (24h)")
        assert errors.tone == "bad"
        assert errors.url == reverse("admin:observability_errorevent_changelist")

    def test_latest_import_counts_only_its_own_errors(self):
        older = CsvImportFactory(original_filename="older.csv")
        newest = CsvImportFactory(original_filename="newest.csv")
        ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, csv_import=older)
        ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, csv_import=newest)
        ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, csv_import=newest)

        latest = stat(dashboard.dashboard_metrics(), "Latest import")

        assert latest.value == "newest.csv"
        assert latest.description == "2 errors"
        assert latest.tone == "warn"

    def test_latest_import_without_one(self):
        latest = stat(dashboard.dashboard_metrics(), "Latest import")
        assert (latest.value, latest.description, latest.url) == ("None yet", "No CSV uploaded yet", None)


class TestErrorsByContextChart:
    def test_stacks_each_day_and_scales_to_the_worst(self):
        today = timezone.now()
        ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN, occurred_at=today)
        ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN, occurred_at=today)
        ErrorEventFactory(context=ErrorEvent.Context.WIKIMEDIA_BLOCK, occurred_at=today)
        ErrorEventFactory(context=ErrorEvent.Context.CSV_ROW, occurred_at=today - timedelta(days=1))

        chart = dashboard.dashboard_metrics()["errors_by_context"]
        latest, previous = chart["days"][-1], chart["days"][-2]

        assert len(chart["days"]) == dashboard.ERROR_WINDOW_DAYS
        assert chart["peak"] == 3
        assert (latest.total, latest.height_percent) == (3, 100.0)
        assert (previous.total, previous.height_percent) == (1, round(1 / 3 * 100, 2))
        assert [(segment.label, segment.count) for segment in latest.segments] == [
            ("Search run", 2),
            ("Wikimedia block", 1),
        ]
        assert sum(segment.height_percent for segment in latest.segments) == pytest.approx(100, abs=0.1)

    def test_only_contexts_that_failed_get_a_legend_entry(self):
        ErrorEventFactory(context=ErrorEvent.Context.CSV_UPLOAD)
        chart = dashboard.dashboard_metrics()["errors_by_context"]
        assert [entry["label"] for entry in chart["legend"]] == ["CSV upload"]

    def test_events_outside_the_window_are_dropped(self):
        ErrorEventFactory(occurred_at=timezone.now() - timedelta(days=dashboard.ERROR_WINDOW_DAYS + 1))
        chart = dashboard.dashboard_metrics()["errors_by_context"]
        assert chart["peak"] == 0
        assert chart["legend"] == []


class TestThroughputChart:
    def test_both_series_are_always_present(self):
        chart = dashboard.dashboard_metrics()["throughput"]
        assert [series["label"] for series in chart["series"]] == ["Completed", "Failed"]
        assert chart["peak"] == 0

    def test_points_span_the_window_and_invert_the_y_axis(self):
        CarSearchFactory(status=CarSearch.Status.COMPLETED)
        CarSearchFactory(status=CarSearch.Status.COMPLETED)
        CarSearchFactory(status=CarSearch.Status.FAILED)

        chart = dashboard.dashboard_metrics()["throughput"]
        completed = next(series for series in chart["series"] if series["label"] == "Completed")
        points = [tuple(float(value) for value in pair.split(",")) for pair in completed["points"].split()]

        assert chart["peak"] == 2
        assert len(points) == dashboard.THROUGHPUT_WINDOW_DAYS
        baseline = float(dashboard.CHART_HEIGHT - dashboard.CHART_INSET)
        assert points[0] == (0.0, baseline), "An empty day sits on the baseline."
        assert points[-1] == (float(dashboard.CHART_WIDTH), float(dashboard.CHART_INSET)), (
            "The peak day sits at the top."
        )
        assert completed["total"] == 2

    def test_running_searches_are_not_charted(self):
        CarSearchFactory(status=CarSearch.Status.RUNNING)
        assert dashboard.dashboard_metrics()["throughput"]["peak"] == 0


class TestLatestFailures:
    def test_newest_first_capped_with_a_link_each(self):
        now = timezone.now()
        for index in range(dashboard.LATEST_FAILURES + 2):
            ErrorEventFactory(message=f"failure {index}", occurred_at=now - timedelta(minutes=index))

        failures = dashboard.dashboard_metrics()["latest_failures"]

        assert len(failures) == dashboard.LATEST_FAILURES
        assert failures[0]["message"] == "failure 0"
        assert failures[0]["url"].startswith("/admin/observability/errorevent/")
        assert failures[0]["color"] == dashboard.CONTEXT_CHART_COLORS[ErrorEvent.Context.SEARCH_RUN]

    def test_falls_back_to_the_exception_message(self):
        ErrorEventFactory(message=None, exception_message="Connection timed out")
        assert dashboard.dashboard_metrics()["latest_failures"][0]["message"] == "Connection timed out"


class TestAdminIndex:
    def test_dashboard_renders_above_the_app_list(self, admin_client):
        ErrorEventFactory(context=ErrorEvent.Context.WIKIMEDIA_BLOCK, message="blocked by Wikimedia")
        CarSearchFactory(status=CarSearch.Status.COMPLETED)

        response = admin_client.get(reverse("admin:index"))
        body = response.content.decode()

        assert response.status_code == 200
        for expected in ("Pipeline health", "Errors (24h)", "Failures by kind", "Searches run", "Latest failures"):
            assert expected in body
        assert "blocked by Wikimedia" in body
        assert body.index("Pipeline health") < body.index("Car searches"), "Health first, then the stock app list."

    def test_empty_database_renders_without_charts(self, admin_client):
        response = admin_client.get(reverse("admin:index"))
        body = response.content.decode()

        assert response.status_code == 200
        assert "No failures recorded in this window." in body
        assert "Nothing has failed" in body

    def test_staff_without_permissions_still_gets_a_page(self, client):
        client.force_login(UserFactory(is_staff=True))
        assert client.get(reverse("admin:index")).status_code == 200


def test_every_error_context_has_a_chart_colour():
    """A context with no colour is a KeyError on the admin landing page."""
    missing = [context for context in ErrorEvent.Context.values if context not in dashboard.CONTEXT_CHART_COLORS]

    assert missing == []


def test_an_unrecognised_context_does_not_take_the_dashboard_down(monkeypatch):
    ErrorEventFactory(context=ErrorEvent.Context.SEARCH_RUN)
    monkeypatch.setattr(dashboard, "CONTEXT_CHART_COLORS", {})

    failures = dashboard.dashboard_metrics()["latest_failures"]

    assert len(failures) == 1
    assert failures[0]["color"] == dashboard.FALLBACK_CHART_COLOR
