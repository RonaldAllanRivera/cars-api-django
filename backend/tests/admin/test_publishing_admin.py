from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse

from apps.images.models import CarImage
from apps.publishing.models import AiUsage, BlogPost, BudgetPeriod
from apps.publishing.services import budget
from apps.publishing.services.publish import describe
from apps.publishing.services.run_chunk import ChunkBlocked, PublishChunkResult
from tests.admin.test_admin import changelist_action, message_texts
from tests.factories import BlogPostFactory, BlogPostMediaFactory, CarImageFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    return client


class TestBlogPostList:
    def test_cost_is_the_sum_of_ai_usage_not_multiplied_by_attachments(self, admin_client):
        post = BlogPostFactory()
        BlogPostMediaFactory(blog_post=post, position=0)
        BlogPostMediaFactory(blog_post=post, position=1)
        AiUsage.objects.create(blog_post=post, model="claude-haiku-4-5", cost_usd=Decimal("0.01"))
        AiUsage.objects.create(blog_post=post, model="claude-haiku-4-5", cost_usd=Decimal("0.02"))

        response = admin_client.get(reverse("admin:publishing_blogpost_changelist"))

        assert response.status_code == 200
        assert "$0.0300" in response.content.decode()


class TestPublishSelected:
    def test_it_publishes_only_the_selection_and_summarises_the_chunk(self, admin_client):
        chosen, other = BlogPostFactory(slug="a"), BlogPostFactory(slug="b")
        result = PublishChunkResult(outcomes=[describe(chosen, "published", images=2)], remaining=0, spent_usd="0.01")

        with mock.patch("apps.publishing.admin.run_chunk", return_value=result) as run:
            response = changelist_action(admin_client, BlogPost, "publish_selected", [chosen])

        assert run.call_args.kwargs == {"post_ids": [chosen.pk]}
        assert other.pk not in run.call_args.kwargs["post_ids"]
        assert any("1 published" in text and "$0.01" in text for text in message_texts(response))

    def test_a_block_is_reported_as_an_error_with_its_reason(self, admin_client):
        post = BlogPostFactory()
        result = PublishChunkResult(
            remaining=1, blocked=ChunkBlocked("budget", None, None, "Monthly AI budget of $10.00 reached")
        )

        with mock.patch("apps.publishing.admin.run_chunk", return_value=result):
            response = changelist_action(admin_client, BlogPost, "publish_selected", [post])

        assert any("Monthly AI budget" in text for text in message_texts(response))

    def test_leftovers_are_pointed_out_so_the_action_can_be_run_again(self, admin_client):
        post = BlogPostFactory()
        result = PublishChunkResult(outcomes=[describe(post, "published")], remaining=3)

        with mock.patch("apps.publishing.admin.run_chunk", return_value=result):
            response = changelist_action(admin_client, BlogPost, "publish_selected", [post])

        assert any("run the action again" in text for text in message_texts(response))


class TestUpdateOnWordPress:
    def test_it_never_writes_new_text(self, admin_client, settings):
        """Posts without text are skipped, so this action cannot spend AI budget."""
        settings.WORDPRESS = {**settings.WORDPRESS, "base_url": "https://wp.test", "username": "u", "app_password": "p"}
        written = BlogPostFactory(slug="written", content="<p>Paid for.</p>", generated_at="2026-09-16T10:00:00Z")
        unwritten = BlogPostFactory(slug="unwritten")
        seen = []

        def fake_publish(post, *, wp, fetcher):
            seen.append(post.pk)
            return describe(post, "updated")

        with (
            mock.patch("apps.publishing.admin.publish.generate_and_publish", side_effect=fake_publish),
            mock.patch("apps.publishing.services.claude_client.generate", side_effect=AssertionError("spent")),
        ):
            response = changelist_action(admin_client, BlogPost, "update_on_wordpress", [written, unwritten])

        assert seen == [written.pk]
        assert any("1 updated" in text and "1 skipped" in text for text in message_texts(response))


class TestRewriteSelected:
    def test_it_discards_the_text_so_the_next_publish_writes_it_again(self, admin_client):
        post = BlogPostFactory(
            content="<p>Old.</p>",
            title="Old title",
            generated_at="2026-09-16T10:00:00Z",
            status=BlogPost.Status.PUBLISHED,
            attempts=3,
            wp_post_id=42,
        )

        with mock.patch("apps.publishing.services.claude_client.generate", side_effect=AssertionError("spent")):
            changelist_action(admin_client, BlogPost, "rewrite_selected", [post])

        post.refresh_from_db()
        assert (post.content, post.generated_at, post.status, post.attempts) == ("", None, BlogPost.Status.PENDING, 0)
        # Kept, so the rewrite updates the same WordPress post rather than creating another.
        assert post.wp_post_id == 42


class TestLedger:
    def test_ai_usage_rows_cannot_be_deleted_because_the_budget_is_built_from_them(self, admin_client):
        usage = AiUsage.objects.create(model="claude-haiku-4-5", cost_usd=Decimal("0.01"))

        response = admin_client.get(reverse("admin:publishing_aiusage_delete", args=[usage.pk]))

        assert response.status_code == 403

    def test_a_drifted_month_can_be_recomputed_from_usage(self, admin_client):
        usage = budget.reserve(
            blog_post=None, estimate_usd=Decimal("0.02"), model="claude-haiku-4-5", rates=budget.current_rates()
        )
        period = BudgetPeriod.objects.get()
        BudgetPeriod.objects.filter(pk=period.pk).update(spent_usd=Decimal("9"))

        changelist_action(admin_client, BudgetPeriod, "recompute_selected", [period])

        period.refresh_from_db()
        assert period.spent_usd == usage.cost_usd


class TestQueueFromImages:
    def test_approved_images_in_the_selection_queue_posts(self, admin_client):
        approved = CarImageFactory(review_status=CarImage.ReviewStatus.APPROVED, make="Toyota", model="RAV4", year=1997)
        pending = CarImageFactory(review_status=CarImage.ReviewStatus.PENDING, make="Honda", model="Civic", year=2001)

        response = changelist_action(admin_client, CarImage, "queue_blog_posts", [approved, pending])

        assert list(BlogPost.objects.values_list("slug", flat=True)) == ["1997-toyota-rav4"]
        assert any("Queued 1 new blog post" in text for text in message_texts(response))
