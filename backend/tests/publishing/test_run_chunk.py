import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.publishing.models import AiUsage, BlogPost, BudgetPeriod
from apps.publishing.services import budget, claude_client, publish, wordpress
from apps.publishing.services import run_chunk as run_chunk_module
from apps.publishing.services.pricing import UnknownModelPriceError
from apps.publishing.services.run_chunk import run_chunk
from tests.factories import BlogPostFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


class FakePublisher:
    """Stands in for publish.generate_and_publish; run_chunk's job is only the loop around it."""

    def __init__(self):
        self.seen: list[int] = []
        self.raises: dict[int, BaseException] = {}

    def __call__(self, post, *, wp, fetcher):
        self.seen.append(post.pk)
        if post.pk in self.raises:
            raise self.raises[post.pk]
        post.status = BlogPost.Status.PUBLISHED
        post.save(update_fields=["status"])
        return publish.describe(post, "published", images=1)


@pytest.fixture
def publisher(monkeypatch):
    fake = FakePublisher()
    monkeypatch.setattr(run_chunk_module.publish, "generate_and_publish", fake)
    return fake


@pytest.fixture
def clock(monkeypatch):
    state = SimpleNamespace(now=0.0, sleeps=[])
    monkeypatch.setattr(
        run_chunk_module, "time", SimpleNamespace(monotonic=lambda: state.now, sleep=state.sleeps.append)
    )
    return state


def posts(count, **fields):
    return [BlogPostFactory(**fields) for _ in range(count)]


class TestQueue:
    def test_runnable_posts_are_worked_through_in_id_order_up_to_the_chunk_size(self, publisher, clock, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_posts_per_chunk": 2}
        first, second, _third = posts(3)

        result = run_chunk()

        assert publisher.seen == [first.pk, second.pk]
        assert result.remaining == 1
        assert [outcome.id for outcome in result.outcomes] == [first.pk, second.pk]

    @pytest.mark.parametrize(
        "status", [BlogPost.Status.PENDING, BlogPost.Status.GENERATED, BlogPost.Status.FAILED, BlogPost.Status.BLOCKED]
    )
    def test_waiting_failed_and_blocked_posts_are_runnable(self, publisher, clock, status):
        (post,) = posts(1, status=status)

        run_chunk()

        assert publisher.seen == [post.pk]

    @pytest.mark.parametrize(
        "status", [BlogPost.Status.PUBLISHED, BlogPost.Status.GENERATING, BlogPost.Status.PUBLISHING]
    )
    def test_published_and_in_flight_posts_are_left_alone(self, publisher, clock, status):
        posts(1, status=status)

        assert run_chunk().outcomes == []

    def test_it_can_be_limited_to_one_import(self, publisher, clock):
        wanted = CsvImportFactory()
        (inside,) = posts(1, csv_import=wanted)
        posts(1, csv_import=CsvImportFactory())

        run_chunk(csv_import_id=wanted.pk)

        assert publisher.seen == [inside.pk]

    def test_it_can_be_limited_to_chosen_posts(self, publisher, clock):
        chosen, _ = posts(2)

        run_chunk(post_ids=[chosen.pk])

        assert publisher.seen == [chosen.pk]

    def test_a_post_that_keeps_failing_to_generate_stops_costing_money(self, publisher, clock, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_generation_attempts": 3}
        (exhausted,) = posts(1, status=BlogPost.Status.FAILED, attempts=3)
        (retrying,) = posts(1, status=BlogPost.Status.FAILED, attempts=2)
        (written,) = posts(
            1, status=BlogPost.Status.FAILED, attempts=3, content="<p>Paid for.</p>", generated_at=timezone.now()
        )

        run_chunk()

        assert publisher.seen == [retrying.pk, written.pk]
        assert exhausted.pk not in publisher.seen

    def test_an_empty_queue_is_not_an_error(self, publisher, clock):
        result = run_chunk()

        assert (result.outcomes, result.remaining, result.blocked) == ([], 0, None)


class TestTimeBox:
    def test_the_first_post_always_runs_then_the_clock_stops_the_chunk(self, publisher, clock, settings, monkeypatch):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "chunk_seconds": 60, "max_posts_per_chunk": 5}
        posts(3)

        def slow(post, *, wp, fetcher):
            clock.now += 70
            return FakePublisher()(post, wp=wp, fetcher=fetcher)

        monkeypatch.setattr(run_chunk_module.publish, "generate_and_publish", slow)
        result = run_chunk()

        assert len(result.outcomes) == 1
        assert result.remaining == 2

    def test_it_pauses_between_posts_but_not_after_the_last(self, publisher, clock, settings):
        settings.CARS_PUBLISHING = {
            **settings.CARS_PUBLISHING,
            "sleep_seconds_between_posts": 0.5,
            "max_posts_per_chunk": 3,
        }
        posts(3)

        run_chunk()

        assert clock.sleeps == [0.5, 0.5]


class TestStopping:
    def test_a_budget_refusal_stops_the_chunk_and_says_why(self, publisher, clock):
        first, _second = posts(2)
        publisher.raises[first.pk] = budget.BudgetExceededError(
            spent_usd=Decimal("9.99"), cap_usd=Decimal("10"), estimate_usd=Decimal("0.04")
        )

        result = run_chunk()

        assert (result.blocked.reason, publisher.seen) == ("budget", [first.pk])
        assert "Monthly AI budget" in result.blocked.message

    def test_a_rate_limited_or_unfunded_claude_api_stops_with_its_wait(self, publisher, clock):
        first, _second = posts(2)
        publisher.raises[first.pk] = claude_client.ClaudeBlockedError(
            "rate limited", status=429, retry_after_seconds=30
        )

        blocked = run_chunk().blocked

        assert (blocked.reason, blocked.status, blocked.retry_after_seconds) == ("claude", 429, 30)
        assert publisher.seen == [first.pk]

    def test_a_model_with_no_known_price_stops_the_chunk(self, publisher, clock):
        (post,) = posts(1)
        publisher.raises[post.pk] = UnknownModelPriceError("no price for claude-future-9")

        assert run_chunk().blocked.reason == "pricing"

    def test_rejected_wordpress_credentials_stop_the_chunk(self, publisher, clock):
        first, _second = posts(2)
        publisher.raises[first.pk] = wordpress.WordPressBlockedError("401", status=401)

        result = run_chunk()

        assert (result.blocked.reason, result.blocked.status, publisher.seen) == ("wordpress", 401, [first.pk])

    def test_unconfigured_wordpress_stops_before_any_post_is_attempted(self, publisher, clock, settings):
        settings.WORDPRESS = {**settings.WORDPRESS, "base_url": ""}
        posts(1)

        result = run_chunk()

        assert (result.blocked.reason, publisher.seen) == ("wordpress", [])
        assert "WORDPRESS_BASE_URL" in result.blocked.message

    def test_one_post_failing_does_not_stop_the_rest(self, publisher, clock):
        first, second = posts(2)
        publisher.raises[first.pk] = claude_client.ClaudeError("cut off")

        result = run_chunk()

        assert [(outcome.id, outcome.outcome) for outcome in result.outcomes] == [
            (first.pk, "failed"),
            (second.pk, "published"),
        ]
        assert result.blocked is None

    def test_the_daily_cap_stops_new_writing_but_still_publishes_text_already_paid_for(
        self, publisher, clock, settings
    ):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_posts_per_day": 1}
        posts(1, status=BlogPost.Status.PUBLISHED, generated_at=timezone.now())
        # The unwritten post comes first, so stopping at it would strand the paid-for one behind it.
        (_unwritten,) = posts(1)
        (written,) = posts(1, status=BlogPost.Status.GENERATED, content="<p>Paid for.</p>", generated_at=timezone.now())

        result = run_chunk()

        assert publisher.seen == [written.pk]
        assert result.blocked.reason == "daily_cap"


class TestRecovery:
    def test_posts_left_mid_run_by_a_killed_worker_become_runnable_again(self, publisher, clock, settings):
        settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "stale_run_minutes": 5}
        (stale,) = posts(1, status=BlogPost.Status.PUBLISHING)
        (fresh,) = posts(1, status=BlogPost.Status.GENERATING)
        BlogPost.objects.filter(pk=stale.pk).update(updated_at=timezone.now() - timedelta(minutes=10))

        run_chunk()

        stale.refresh_from_db()
        fresh.refresh_from_db()
        assert publisher.seen == [stale.pk]
        assert fresh.status == BlogPost.Status.GENERATING

    def test_abandoned_ai_reservations_are_reconciled_first(self, publisher, clock, time_machine):
        time_machine.move_to("2026-09-16T10:00:00Z", tick=False)
        usage = budget.reserve(
            blog_post=None, estimate_usd=Decimal("0.01"), model="claude-haiku-4-5", rates=budget.current_rates()
        )
        time_machine.move_to("2026-09-16T10:30:00Z", tick=False)

        run_chunk()

        usage.refresh_from_db()
        assert usage.status == AiUsage.Status.ABANDONED


class TestResult:
    def test_the_month_to_date_spend_is_reported(self, publisher, clock):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("1.25"))

        assert Decimal(run_chunk().spent_usd) == Decimal("1.25")

    def test_the_result_serialises_to_plain_data(self, publisher, clock):
        _first, second = posts(2)
        publisher.raises[second.pk] = budget.BudgetExceededError(
            spent_usd=Decimal("1"), cap_usd=Decimal("1"), estimate_usd=Decimal("0.1")
        )

        payload = run_chunk().as_dict()

        assert json.loads(json.dumps(payload)) == payload
        assert payload["blocked"]["reason"] == "budget"
        assert payload["outcomes"][0]["outcome"] == "published"
