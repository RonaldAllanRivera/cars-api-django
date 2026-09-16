from decimal import Decimal
from unittest import mock

import pytest

from apps.accounts import abilities
from apps.images.models import CarImage
from apps.publishing.models import BlogPost, BudgetPeriod
from apps.publishing.services import budget
from apps.publishing.services.publish import describe
from apps.publishing.services.run_chunk import ChunkBlocked, PublishChunkResult
from tests.factories import BlogPostFactory, BlogPostMediaFactory, CarImageFactory, CsvImportFactory

pytestmark = pytest.mark.django_db


class TestAbilities:
    def test_blog_abilities_are_privileged_and_never_issued_by_default(self):
        for ability in (abilities.BLOG_READ, abilities.BLOG_WRITE, abilities.BLOG_PUBLISH):
            assert ability in abilities.ALL
            assert ability not in abilities.DEFAULT

    @pytest.mark.parametrize(
        ("method", "path", "needed"),
        [
            ("get", "/api/v1/blog-posts", abilities.BLOG_READ),
            ("get", "/api/v1/blog-posts/budget", abilities.BLOG_READ),
            ("post", "/api/v1/blog-posts/sync", abilities.BLOG_WRITE),
            ("post", "/api/v1/blog-posts/run-chunk", abilities.BLOG_PUBLISH),
        ],
    )
    def test_each_endpoint_needs_its_ability(self, client, acting_as, method, path, needed):
        acting_as([ability for ability in abilities.ALL if ability != needed])

        assert getattr(client, method)(path, {}, format="json").status_code == 403

    def test_spending_needs_the_publish_ability_not_just_write(self, client, acting_as):
        acting_as([abilities.BLOG_READ, abilities.BLOG_WRITE])

        assert client.post("/api/v1/blog-posts/run-chunk", {}, format="json").status_code == 403


class TestList:
    def test_posts_are_listed_newest_first_with_their_image_count(self, client, acting_as):
        acting_as([abilities.BLOG_READ])
        older = BlogPostFactory(slug="older")
        newer = BlogPostFactory(slug="newer", status=BlogPost.Status.PUBLISHED, wp_post_id=42)
        BlogPostMediaFactory(blog_post=newer)

        body = client.get("/api/v1/blog-posts").json()

        assert [row["id"] for row in body["data"]] == [newer.pk, older.pk]
        assert (body["data"][0]["status"], body["data"][0]["wp_post_id"], body["data"][0]["images_count"]) == (
            "published",
            42,
            1,
        )
        assert "content" not in body["data"][0]

    def test_posts_can_be_filtered_by_status_and_import(self, client, acting_as):
        acting_as([abilities.BLOG_READ])
        wanted = CsvImportFactory()
        match = BlogPostFactory(slug="a", status=BlogPost.Status.FAILED, csv_import=wanted)
        BlogPostFactory(slug="b", status=BlogPost.Status.FAILED)
        BlogPostFactory(slug="c", csv_import=wanted)

        body = client.get("/api/v1/blog-posts", {"status": "failed", "csv_import_id": wanted.pk}).json()

        assert [row["id"] for row in body["data"]] == [match.pk]

    def test_an_unknown_status_is_a_validation_error(self, client, acting_as):
        acting_as([abilities.BLOG_READ])

        assert client.get("/api/v1/blog-posts", {"status": "nonsense"}).status_code == 422


class TestDetail:
    def test_the_detail_carries_the_article_seo_and_media(self, client, acting_as):
        acting_as([abilities.BLOG_READ])
        post = BlogPostFactory(content="<p>Article.</p>", seo_title="SEO title")
        BlogPostMediaFactory(blog_post=post, wp_media_id=7, is_featured=True)

        data = client.get(f"/api/v1/blog-posts/{post.pk}").json()["data"]

        assert (data["content"], data["seo_title"]) == ("<p>Article.</p>", "SEO title")
        assert [(item["wp_media_id"], item["is_featured"]) for item in data["media"]] == [(7, True)]


class TestBudget:
    def test_the_months_spend_is_reported_against_the_cap(self, client, acting_as, settings):
        acting_as([abilities.BLOG_READ])
        settings.AI_BUDGET = {**settings.AI_BUDGET, "monthly_usd": 10.0}
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("2.5"), calls=40)

        data = client.get("/api/v1/blog-posts/budget").json()["data"]

        assert data == {
            "month": budget.month_start().isoformat(),
            "spent_usd": "2.500000",
            "cap_usd": "10.0",
            "remaining_usd": "7.500000",
            "percent_used": 25,
            "calls": 40,
        }


class TestSync:
    def test_it_queues_posts_from_approved_images(self, client, acting_as):
        acting_as([abilities.BLOG_WRITE])
        CarImageFactory(review_status=CarImage.ReviewStatus.APPROVED, make="Toyota", model="RAV4", year=1997)

        response = client.post("/api/v1/blog-posts/sync", {}, format="json")

        assert response.status_code == 200
        assert response.json()["data"] == {"created": 1, "existing": 0}
        assert BlogPost.objects.get().slug == "1997-toyota-rav4"

    def test_an_unknown_import_is_a_validation_error(self, client, acting_as):
        acting_as([abilities.BLOG_WRITE])

        assert client.post("/api/v1/blog-posts/sync", {"csv_import_id": 999999}, format="json").status_code == 422


class TestRunChunk:
    def test_it_runs_one_chunk_for_the_requested_scope(self, client, acting_as):
        acting_as([abilities.BLOG_PUBLISH])
        post = BlogPostFactory()
        result = PublishChunkResult(outcomes=[describe(post, "published", images=2)], remaining=0, spent_usd="0.01")

        with mock.patch("api.v1.views.blog_posts.run_chunk", return_value=result) as run:
            response = client.post("/api/v1/blog-posts/run-chunk", {"post_ids": [post.pk]}, format="json")

        assert response.status_code == 200
        assert run.call_args.kwargs == {"csv_import_id": None, "post_ids": [post.pk]}
        body = response.json()
        assert (body["remaining"], body["blocked"], body["outcomes"][0]["outcome"]) == (0, None, "published")

    def test_a_block_is_a_successful_response_that_ends_the_clients_loop(self, client, acting_as):
        """Like /searches/run-chunk: the client stops on `blocked`, so the block is data, not an HTTP error."""
        acting_as([abilities.BLOG_PUBLISH])
        result = PublishChunkResult(
            remaining=4, blocked=ChunkBlocked("budget", None, None, "Monthly AI budget reached")
        )

        with mock.patch("api.v1.views.blog_posts.run_chunk", return_value=result):
            response = client.post("/api/v1/blog-posts/run-chunk", {}, format="json")

        assert response.status_code == 200
        assert response.json()["blocked"]["reason"] == "budget"

    def test_too_many_post_ids_is_a_validation_error(self, client, acting_as):
        acting_as([abilities.BLOG_PUBLISH])

        response = client.post("/api/v1/blog-posts/run-chunk", {"post_ids": list(range(1, 60))}, format="json")

        assert response.status_code == 422

    def test_spending_calls_have_their_own_tight_throttle(self, client, acting_as, throttle_rate):
        acting_as([abilities.BLOG_PUBLISH])
        throttle_rate("publish", "1/min")
        result = PublishChunkResult()

        with mock.patch("api.v1.views.blog_posts.run_chunk", return_value=result):
            first = client.post("/api/v1/blog-posts/run-chunk", {}, format="json")
            second = client.post("/api/v1/blog-posts/run-chunk", {}, format="json")

        assert (first.status_code, second.status_code) == (200, 429)
