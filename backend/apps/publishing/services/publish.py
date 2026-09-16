"""
Writes, illustrates and publishes one blog post.

Three stages, each saved before the next can fail:

1. Write: Claude writes the article, missing SEO fields are filled, and the post
   is saved as `generated`. A post that already has its text skips this stage,
   so no later failure ever pays for the same words twice.
2. Illustrate: approved images are uploaded, skipping any already on WordPress.
3. Publish: a new post is created as a draft; an existing one is updated without
   touching its status, so a post an editor already put live stays live.

The WordPress id is saved the moment a post is created, before anything else can
fail, so a crash leads to an update next time rather than a second post. When a
create may have succeeded without the response arriving, the next run finds the
draft by its slug instead of creating another.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal

import httpx
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags

from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.publishing.models import BlogPost
from apps.publishing.services import claude_client, media, seo
from apps.publishing.services.budget import BudgetExceededError
from apps.publishing.services.gallery import GalleryImage, compose, gallery_images
from apps.publishing.services.pricing import UnknownModelPriceError
from apps.publishing.services.prompt import PromptFacts, build_prompt
from apps.publishing.services.wordpress import (
    WordPressBlockedError,
    WordPressClient,
    WordPressError,
    WordPressNotFoundError,
)

# Figures the prompt forbids because the pipeline never supplies them: prices,
# power and economy, and mileage milestones.
QUOTED_FIGURES = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"
    r"|\b\d[\d,.]*\s?(?:hp|bhp|horsepower|mpg|kW|Nm|lb-ft)\b"
    r"|\b(?:\d{1,3}(?:,\d{3})+|\d{4,})\s?miles\b",
    re.IGNORECASE,
)


@dataclass
class PostOutcome:
    id: int
    slug: str
    year: int
    make: str
    model: str | None
    outcome: str  # "published" | "updated" | "skipped" | "failed"
    wp_post_id: int | None
    images: int
    cost_usd: str


def generate_and_publish(post: BlogPost, *, wp: WordPressClient, fetcher: httpx.Client) -> PostOutcome:
    """
    Raises BudgetExceededError, UnknownModelPriceError, ClaudeBlockedError and
    WordPressBlockedError, which stop a run; any other failure is recorded on
    the post and raised for the run to count.
    """
    cost = Decimal("0")
    if not (post.generated_at and post.content):
        cost = _write(post)
    media.sync(post, wp=wp, fetcher=fetcher)
    return _publish(post, wp, cost)


def describe(post: BlogPost, outcome: str, *, images: int = 0, cost: Decimal = Decimal("0")) -> PostOutcome:
    return PostOutcome(
        id=post.pk,
        slug=post.slug,
        year=post.year,
        make=post.make,
        model=post.model,
        outcome=outcome,
        wp_post_id=post.wp_post_id,
        images=images,
        cost_usd=str(cost),
    )


def _write(post: BlogPost) -> Decimal:
    waiting_status = post.status
    post.status = BlogPost.Status.GENERATING
    post.attempts += 1
    post.save(update_fields=["status", "attempts", "updated_at"])

    prompt = build_prompt(
        _facts(post),
        homepage_url=settings.WORDPRESS["homepage_url"],
        site_name=settings.WORDPRESS["site_name"],
    )
    try:
        generation = claude_client.generate(prompt, blog_post=post)
    except BudgetExceededError as refused:
        _set_status(post, BlogPost.Status.BLOCKED, str(refused))
        raise
    except (claude_client.ClaudeBlockedError, UnknownModelPriceError) as error:
        # Not this post's fault: it waits in the queue as it was.
        _set_status(post, waiting_status, str(error))
        raise
    except Exception as error:
        _set_status(post, BlogPost.Status.FAILED, str(error) or type(error).__name__)
        raise

    filled = seo.fill_gaps(
        title=generation.title,
        content=generation.content,
        seo_title=generation.seo_title,
        seo_description=generation.seo_description,
        seo_keywords=generation.seo_keywords,
        year=post.year,
        make=post.make,
        model=post.model,
    )
    post.title = generation.title[: BlogPost._meta.get_field("title").max_length]
    post.content = generation.content
    post.seo_title = filled.seo_title
    post.seo_description = filled.seo_description
    post.seo_keywords = filled.seo_keywords
    post.ai_model = generation.model[: BlogPost._meta.get_field("ai_model").max_length]
    post.generated_at = timezone.now()
    post.status = BlogPost.Status.GENERATED
    post.last_error = None
    # The commit point: from here the words are paid for and kept.
    post.save()
    _flag_quoted_figures(post)
    return generation.cost_usd


def _facts(post: BlogPost) -> PromptFacts:
    """
    Only what is true of every car of this make, model and year. A search's
    colour and transmission describe which photos were wanted, not the vehicle.
    """
    titles = tuple(image.title for image in media.approved_images(post))
    return PromptFacts(year=post.year, make=post.make, model=post.model, image_titles=titles)


def _flag_quoted_figures(post: BlogPost) -> None:
    """
    Flags rather than discards: a discarded post would be paid for again on
    every run, and every post is a draft a person reviews before it goes live.
    """
    text = " ".join(strip_tags(post.content.replace("<", " <")).split())
    figures = sorted(set(QUOTED_FIGURES.findall(text)))
    if figures:
        error_logger.record(
            ErrorEvent.Context.AI_GENERATION,
            f"{post} quotes figures the pipeline did not supply; check them before publishing.",
            blog_post=post,
            car_search=post.car_search_id,
            severity=ErrorEvent.Severity.WARNING,
            details={"figures": figures},
        )


def _publish(post: BlogPost, wp: WordPressClient, cost: Decimal) -> PostOutcome:
    images = gallery_images(post)
    featured = next((image.wp_media_id for image in images if image.featured), None)
    payload = _payload(post, images, featured)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    if post.status == BlogPost.Status.PUBLISHED and post.wp_post_id and post.images_fingerprint == fingerprint:
        return describe(post, "skipped", images=len(images), cost=cost)

    # A previous attempt that reached WordPress may have created the post without the response arriving.
    may_exist = post.status in (BlogPost.Status.PUBLISHING, BlogPost.Status.FAILED) and not post.wp_post_id
    waiting_status = post.status
    _set_status(post, BlogPost.Status.PUBLISHING)
    try:
        target = post.wp_post_id
        if not target and may_exist:
            found = wp.find_post_by_slug(post.slug)
            if found:
                target = found["id"]
                _remember_wp_id(post, target)

        result, outcome = None, "updated"
        if target:
            try:
                # No status: an editor may already have put this post live.
                result = wp.update_post(target, payload)
            except WordPressNotFoundError:
                _remember_wp_id(post, None)
                target = None
        if not target:
            result = wp.create_post({**payload, "status": settings.WORDPRESS["post_status"]})
            # Saved alone and first: a crash after this updates next time instead of duplicating.
            _remember_wp_id(post, result["id"])
            outcome = "published"
    except WordPressBlockedError as error:
        _set_status(post, waiting_status, str(error))
        raise
    except WordPressError as error:
        _set_status(post, BlogPost.Status.FAILED, str(error))
        error_logger.record(
            ErrorEvent.Context.WORDPRESS_PUBLISH,
            error,
            blog_post=post,
            car_search=post.car_search_id,
            details={
                "http_status": error.status,
                "code": error.code,
                "may_have_succeeded": error.may_have_succeeded,
                "response_excerpt": error.response_excerpt,
            },
        )
        raise

    _mark_published(post, result, featured=featured, fingerprint=fingerprint)
    return describe(post, outcome, images=len(images), cost=cost)


def _payload(post: BlogPost, images: list[GalleryImage], featured: int | None) -> dict:
    config = settings.WORDPRESS
    payload = {
        "title": post.title,
        "slug": post.slug,
        "content": compose(post.content, images, use_blocks=config["use_blocks"]),
        # Registered for REST by the used-cars-search plugin; its hook mirrors the SEO keys to Yoast and Rank Math.
        "meta": {
            "_ucs_seo_title": post.seo_title,
            "_ucs_seo_description": post.seo_description,
            "_ucs_seo_keywords": post.seo_keywords,
            "ucs_year": post.year,
            "ucs_make": post.make,
            "ucs_model": post.model or "",
        },
    }
    if featured:
        payload["featured_media"] = featured
    # Sent only when configured, so an unset value never clears an editor's choice.
    if config["default_category_id"]:
        payload["categories"] = [config["default_category_id"]]
    if config["author_id"]:
        payload["author"] = config["author_id"]
    return payload


def _mark_published(post: BlogPost, result: dict, *, featured: int | None, fingerprint: str) -> None:
    post.wp_link = result.get("link") or post.wp_link
    post.wp_status = str(result.get("status") or "")
    post.featured_media_id = featured
    post.images_fingerprint = fingerprint
    post.published_at = post.published_at or timezone.now()
    post.status = BlogPost.Status.PUBLISHED
    post.last_error = None
    post.save()


def _remember_wp_id(post: BlogPost, wp_post_id: int | None) -> None:
    BlogPost.objects.filter(pk=post.pk).update(wp_post_id=wp_post_id, updated_at=timezone.now())
    post.wp_post_id = wp_post_id


def _set_status(post: BlogPost, status: str, error: str | None = None) -> None:
    post.status = status
    post.last_error = error
    post.save(update_fields=["status", "last_error", "updated_at"])
