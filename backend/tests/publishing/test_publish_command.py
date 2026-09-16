from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.images.models import CarImage
from apps.publishing.models import BlogPost
from apps.publishing.services import budget
from apps.publishing.services import run_chunk as run_chunk_module
from apps.publishing.services.publish import describe
from tests.factories import BlogPostFactory, CarImageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def publisher(monkeypatch):
    calls = []

    def fake(post, *, wp, fetcher):
        calls.append(post.pk)
        post.status = BlogPost.Status.PUBLISHED
        post.save(update_fields=["status"])
        return describe(post, "published", images=2, cost=Decimal("0.009768"))

    monkeypatch.setattr(run_chunk_module.publish, "generate_and_publish", fake)
    return calls


def run(*args) -> str:
    out = StringIO()
    call_command("publish_blog_posts", *args, stdout=out)
    return out.getvalue()


def test_by_default_it_runs_a_single_chunk_so_one_command_spends_a_bounded_amount(publisher, settings):
    settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_posts_per_chunk": 1}
    BlogPostFactory(slug="a")
    BlogPostFactory(slug="b")

    output = run()

    assert len(publisher) == 1
    assert "published" in output
    assert "1 post(s) still waiting" in output


def test_more_chunks_keep_going_until_nothing_is_left(publisher, settings):
    settings.CARS_PUBLISHING = {**settings.CARS_PUBLISHING, "max_posts_per_chunk": 1}
    for slug in ("a", "b", "c"):
        BlogPostFactory(slug=slug)

    output = run("--chunks", "10")

    assert len(publisher) == 3
    assert "0 post(s) still waiting" in output


def test_seeding_queues_posts_from_approved_images_first(publisher):
    CarImageFactory(review_status=CarImage.ReviewStatus.APPROVED, make="Toyota", model="RAV4", year=1997)

    output = run("--seed")

    assert "Queued 1 new post(s)" in output
    assert BlogPost.objects.get().slug == "1997-toyota-rav4"


def test_a_block_stops_the_command_and_says_why(monkeypatch, settings):
    BlogPostFactory(slug="a")
    BlogPostFactory(slug="b")

    def refuse(post, *, wp, fetcher):
        raise budget.BudgetExceededError(spent_usd=Decimal("10"), cap_usd=Decimal("10"), estimate_usd=Decimal("0.04"))

    monkeypatch.setattr(run_chunk_module.publish, "generate_and_publish", refuse)

    output = run("--chunks", "10")

    assert "Stopped (budget)" in output
    assert "Monthly AI budget" in output


def test_the_months_ai_spend_is_reported(publisher):
    BlogPostFactory(slug="a")

    assert "AI spend this month: $" in run()
