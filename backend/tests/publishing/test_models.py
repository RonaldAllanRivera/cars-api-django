from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.publishing.models import AiUsage, BlogPost, BlogPostMedia, BudgetPeriod
from tests.factories import BlogPostFactory, BlogPostMediaFactory, CarImageFactory

pytestmark = pytest.mark.django_db


class TestBlogPost:
    def test_a_post_is_named_by_its_vehicle(self):
        post = BlogPostFactory(year=1997, make="Toyota", model="RAV4")

        assert str(post) == "1997 Toyota RAV4"

    def test_a_post_without_a_model_is_still_named(self):
        post = BlogPostFactory(year=1997, make="Toyota", model=None, slug="1997-toyota")

        assert str(post) == "1997 Toyota"

    def test_the_same_vehicle_cannot_be_queued_twice(self):
        BlogPostFactory(slug="1997-toyota-rav4")

        with pytest.raises(IntegrityError):
            BlogPostFactory(slug="1997-toyota-rav4")

    def test_a_new_post_has_spent_nothing_and_reached_nowhere(self):
        post = BlogPostFactory()

        assert post.status == BlogPost.Status.PENDING
        assert post.wp_post_id is None
        assert post.generated_at is None
        assert post.published_at is None

    def test_posts_are_listed_newest_first(self):
        older = BlogPostFactory(slug="a")
        newer = BlogPostFactory(slug="b")

        assert list(BlogPost.objects.all()) == [newer, older]

    def test_deleting_a_search_keeps_a_post_that_already_exists_on_wordpress(self):
        post = BlogPostFactory(wp_post_id=42)
        search = post.car_search

        search.delete()
        post.refresh_from_db()

        assert post.wp_post_id == 42
        assert post.car_search_id is None


class TestBlogPostMedia:
    def test_an_image_cannot_be_attached_to_a_post_twice(self):
        media = BlogPostMediaFactory()

        with pytest.raises(IntegrityError):
            BlogPostMediaFactory(blog_post=media.blog_post, car_image=media.car_image)

    def test_the_same_image_can_appear_on_two_different_posts(self):
        image = CarImageFactory()
        BlogPostMediaFactory(car_image=image, blog_post=BlogPostFactory(slug="a"))
        BlogPostMediaFactory(car_image=image, blog_post=BlogPostFactory(slug="b"))

        assert BlogPostMedia.objects.filter(car_image=image).count() == 2

    def test_media_is_ordered_by_position_not_insertion(self):
        post = BlogPostFactory()
        second = BlogPostMediaFactory(blog_post=post, position=1)
        first = BlogPostMediaFactory(blog_post=post, position=0)

        assert list(post.media.all()) == [first, second]

    def test_media_names_the_file_and_the_attachment_it_became(self):
        media = BlogPostMediaFactory(filename="1997-toyota-rav4.jpg", wp_media_id=7)

        assert str(media) == "1997-toyota-rav4.jpg (wp #7)"


class TestAiUsage:
    def test_money_is_stored_exactly(self):
        """A budget compared with accumulated float error is not a budget."""
        usage = AiUsage.objects.create(model="claude-haiku-4-5", cost_usd=Decimal("0.000123"))
        usage.refresh_from_db()

        assert usage.cost_usd == Decimal("0.000123")

    def test_a_usage_row_reads_as_tokens_and_dollars(self):
        usage = AiUsage.objects.create(model="claude-haiku-4-5", total_tokens=1234, cost_usd=Decimal("0.002500"))

        assert str(usage) == "claude-haiku-4-5 1234 tok $0.002500"

    def test_a_usage_row_starts_reserved(self):
        assert AiUsage.objects.create(model="claude-haiku-4-5").status == AiUsage.Status.RESERVED

    def test_deleting_a_post_keeps_its_spend_on_record(self):
        post = BlogPostFactory()
        usage = AiUsage.objects.create(model="claude-haiku-4-5", blog_post=post, cost_usd=Decimal("0.01"))

        post.delete()
        usage.refresh_from_db()

        assert usage.cost_usd == Decimal("0.01")
        assert usage.blog_post_id is None


class TestBudgetPeriod:
    def test_a_period_reads_as_its_month_and_spend(self):
        period = BudgetPeriod.objects.create(month=date(2026, 9, 1), spent_usd=Decimal("3.4"))
        period.refresh_from_db()

        assert str(period) == "2026-09: $3.400000"

    def test_a_month_has_at_most_one_period(self):
        month = timezone.now().date().replace(day=1)
        BudgetPeriod.objects.create(month=month)

        with pytest.raises(IntegrityError):
            BudgetPeriod.objects.create(month=month)
