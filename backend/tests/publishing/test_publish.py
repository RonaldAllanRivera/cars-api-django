"""
Claude, Commons and WordPress are all faked: nothing here spends tokens or
touches a real site. Claude runs on httpx2 (the SDK's transport) and is faked
there; Commons and WordPress run on httpx and are faked with respx.
"""

import json
from decimal import Decimal

import httpx
import pytest
import respx

from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.publishing.models import BlogPost, BudgetPeriod
from apps.publishing.services import budget, claude_client, media, publish, seo, wordpress
from tests.exports.images import encode_image
from tests.factories import BlogPostFactory, CarImageFactory, CarSearchFactory
from tests.publishing.fakes import FIELDS, api_error, message

pytestmark = pytest.mark.django_db

WP = "https://wp.test/wp-json/wp/v2"
CREATED = {"id": 42, "link": "https://wp.test/?p=42", "status": "draft", "slug": "1997-toyota-rav4"}


@pytest.fixture
def http():
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def site(http):
    """A WordPress site that accepts uploads and creates post 42."""

    class Site:
        media = http.post(f"{WP}/media").mock(
            return_value=httpx.Response(201, json={"id": 7, "source_url": "https://wp.test/uploads/7.jpg"})
        )
        create = http.post(f"{WP}/posts").mock(return_value=httpx.Response(201, json=CREATED))
        update = http.post(f"{WP}/posts/42").mock(
            return_value=httpx.Response(200, json={**CREATED, "status": "publish"})
        )
        find = http.get(f"{WP}/posts").mock(return_value=httpx.Response(200, json=[]))

    return Site


@pytest.fixture
def post(http):
    search = CarSearchFactory(
        make="Toyota", model="RAV4", from_year=1997, to_year=1997, color="Red", transmission="Manual"
    )
    url = "https://upload.wikimedia.org/commons/1.jpg"
    http.get(url).mock(return_value=httpx.Response(200, content=encode_image(64, 48)))
    CarImageFactory(
        car_search=search,
        review_status=CarImage.ReviewStatus.APPROVED,
        source_url=url,
        title="File:1997 Toyota RAV4 front.jpg",
        license="CC BY-SA 4.0",
        attribution="Jane Photographer",
    )
    return BlogPostFactory(car_search=search, make="Toyota", model="RAV4", year=1997, slug="1997-toyota-rav4")


def run(post):
    with wordpress.client() as wp, media.fetch_client() as fetcher:
        return publish.generate_and_publish(post, wp=wp, fetcher=fetcher)


def sent(route, index=-1) -> dict:
    return json.loads(route.calls[index].request.content)


class TestHappyPath:
    def test_a_new_post_is_written_illustrated_and_created_as_a_draft(self, messages_api, site, post):
        messages_api.queue(message())

        outcome = run(post)

        post.refresh_from_db()
        payload = sent(site.create)
        assert (outcome.outcome, outcome.wp_post_id, outcome.images) == ("published", 42, 1)
        assert (post.status, post.wp_post_id, post.wp_link, post.featured_media_id) == (
            BlogPost.Status.PUBLISHED,
            42,
            "https://wp.test/?p=42",
            7,
        )
        assert (payload["status"], payload["slug"], payload["title"], payload["featured_media"]) == (
            "draft",
            "1997-toyota-rav4",
            FIELDS["title"],
            7,
        )
        assert payload["content"].startswith(FIELDS["content"])
        assert "Image credits" in payload["content"]
        # Unset category and author are left out, so an editor's choice is never cleared.
        assert "categories" not in payload
        assert "author" not in payload

    def test_seo_and_car_details_go_to_the_plugins_rest_meta(self, messages_api, site, post):
        messages_api.queue(message())

        run(post)

        assert sent(site.create)["meta"] == {
            "_ucs_seo_title": FIELDS["seo_title"],
            "_ucs_seo_description": FIELDS["seo_description"],
            "_ucs_seo_keywords": "used toyota rav4, 1997 rav4",
            "ucs_year": 1997,
            "ucs_make": "Toyota",
            "ucs_model": "RAV4",
        }

    def test_missing_seo_fields_are_filled_before_anything_is_saved(self, messages_api, site, post):
        messages_api.queue(message({**FIELDS, "seo_title": "", "seo_keywords": []}))

        run(post)

        post.refresh_from_db()
        expected = seo.fill_gaps(
            title=FIELDS["title"],
            content=FIELDS["content"],
            seo_title="",
            seo_description="",
            seo_keywords=[],
            year=1997,
            make="Toyota",
            model="RAV4",
        )
        assert (post.seo_title, post.seo_keywords) == (expected.seo_title, expected.seo_keywords)

    def test_category_and_author_are_sent_only_when_configured(self, messages_api, site, post, settings):
        messages_api.queue(message())
        settings.WORDPRESS = {**settings.WORDPRESS, "default_category_id": 5, "author_id": 3}

        run(post)

        payload = sent(site.create)
        assert (payload["categories"], payload["author"]) == ([5], 3)

    def test_the_prompt_carries_only_facts_about_the_vehicle_not_search_filters(self, messages_api, site, post):
        """The search asked for red manual photos; that does not make every 1997 RAV4 red or manual."""
        messages_api.queue(message())

        run(post)

        facts = json.loads(messages_api.body()["messages"][0]["content"])
        assert facts["vehicle"] == {"year": 1997, "make": "Toyota", "model": "RAV4"}
        assert facts["image_subjects"] == ["1997 Toyota RAV4 front"]


class TestNeverPayTwice:
    def test_a_wordpress_failure_after_generation_never_pays_for_the_words_again(self, messages_api, site, post):
        messages_api.queue(message())
        site.create.mock(return_value=httpx.Response(400, json={"code": "rest_invalid_param"}))

        with pytest.raises(wordpress.WordPressError):
            run(post)

        post.refresh_from_db()
        assert (post.status, post.content != "") == (BlogPost.Status.FAILED, True)
        site.create.mock(return_value=httpx.Response(201, json=CREATED))

        outcome = run(post)

        assert (outcome.outcome, messages_api.call_count) == ("published", 1)

    def test_the_wordpress_id_is_saved_before_anything_else_can_fail(self, messages_api, site, post, monkeypatch):
        messages_api.queue(message())

        def crash(*args, **kwargs):
            raise RuntimeError("worker killed")

        monkeypatch.setattr(publish, "_mark_published", crash)
        with pytest.raises(RuntimeError):
            run(post)

        post.refresh_from_db()
        assert post.wp_post_id == 42
        monkeypatch.undo()

        run(post)

        assert (site.create.call_count, site.update.call_count) == (1, 1)

    def test_a_post_that_may_have_been_created_is_found_by_slug_instead_of_created_twice(
        self, messages_api, site, post
    ):
        messages_api.queue(message())
        site.create.mock(return_value=httpx.Response(502))

        with pytest.raises(wordpress.WordPressError):
            run(post)

        # The 502 hid a successful create: the draft exists.
        site.find.mock(return_value=httpx.Response(200, json=[CREATED]))
        site.create.mock(return_value=httpx.Response(201, json=CREATED))

        outcome = run(post)

        assert (site.create.call_count, site.update.call_count, outcome.wp_post_id) == (1, 1, 42)


class TestUpdates:
    def test_an_update_never_changes_the_status_an_editor_chose(self, messages_api, site, post):
        """Sending "draft" again would unpublish a post an editor already put live."""
        post.status, post.wp_post_id = BlogPost.Status.FAILED, 42
        _mark_generated(post)

        run(post)

        assert "status" not in sent(site.update)
        assert site.create.call_count == 0

    def test_a_post_deleted_in_wordpress_is_created_again(self, messages_api, http, site, post):
        post.status, post.wp_post_id = BlogPost.Status.FAILED, 99
        _mark_generated(post)
        http.post(f"{WP}/posts/99").mock(return_value=httpx.Response(404, json={"code": "rest_post_invalid_id"}))

        outcome = run(post)

        post.refresh_from_db()
        assert (outcome.outcome, site.create.call_count, post.wp_post_id) == ("published", 1, 42)

    def test_an_unchanged_published_post_is_skipped_without_calling_wordpress(self, messages_api, site, post):
        messages_api.queue(message())
        run(post)
        calls_before = site.create.call_count + site.update.call_count

        outcome = run(post)

        assert outcome.outcome == "skipped"
        assert site.create.call_count + site.update.call_count == calls_before
        assert messages_api.call_count == 1


class TestStopping:
    def test_a_budget_refusal_blocks_the_post_and_stops_the_run(self, messages_api, site, post):
        BudgetPeriod.objects.create(month=budget.month_start(), spent_usd=Decimal("9.9999"))
        messages_api.queue(message())

        with pytest.raises(budget.BudgetExceededError):
            run(post)

        post.refresh_from_db()
        assert post.status == BlogPost.Status.BLOCKED
        assert "Monthly AI budget" in post.last_error

    def test_a_rate_limited_claude_api_leaves_the_post_waiting_rather_than_failed(self, messages_api, site, post):
        messages_api.queue(api_error(429, "rate_limit_error"))

        with pytest.raises(claude_client.ClaudeBlockedError):
            run(post)

        post.refresh_from_db()
        assert post.status == BlogPost.Status.PENDING

    def test_a_failed_generation_is_marked_failed_and_counted(self, messages_api, site, post):
        messages_api.queue(api_error(400, "invalid_request_error"))

        with pytest.raises(claude_client.ClaudeError):
            run(post)

        post.refresh_from_db()
        assert (post.status, post.attempts, site.create.call_count) == (BlogPost.Status.FAILED, 1, 0)
        assert post.last_error

    def test_rejected_wordpress_credentials_keep_the_paid_for_text_and_stop(self, messages_api, http, post):
        messages_api.queue(message())
        http.post(f"{WP}/media").mock(return_value=httpx.Response(401, json={"code": "rest_cannot_create"}))

        with pytest.raises(wordpress.WordPressBlockedError):
            run(post)

        post.refresh_from_db()
        assert (post.status, post.title) == (BlogPost.Status.GENERATED, FIELDS["title"])


class TestReview:
    def test_quoted_figures_are_flagged_for_the_reviewer_not_discarded(self, messages_api, site, post):
        """Discarding would re-spend on every run; every post is a draft a person reviews anyway."""
        content = "<p>Asking $4,999 with 150 hp and 28 mpg, and many pass 200,000 miles.</p>"
        messages_api.queue(message({**FIELDS, "content": content}))

        outcome = run(post)

        event = ErrorEvent.objects.get(context=ErrorEvent.Context.AI_GENERATION)
        assert outcome.outcome == "published"
        assert event.severity == ErrorEvent.Severity.WARNING
        assert set(event.details["figures"]) == {"$4,999", "150 hp", "28 mpg", "200,000 miles"}


def _mark_generated(post):
    from django.utils import timezone

    post.title, post.content = FIELDS["title"], FIELDS["content"]
    post.seo_title, post.seo_description, post.seo_keywords = "t", "d", "k"
    post.generated_at = timezone.now()
    post.save()
