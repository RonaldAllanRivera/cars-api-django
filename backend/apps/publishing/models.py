"""
The blog posts generated from reviewed car images, and what they cost.

A post moves pending -> generating -> generated -> publishing -> published.
`generated` is a durable commit point: the AI text is stored before WordPress is
touched, so a failed publish is retried without paying for the words again.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class BlogPost(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        # The two -ing states mark a run in flight, so a killed worker leaves a trail.
        GENERATING = "generating", "Generating"
        GENERATED = "generated", "Generated"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Budget blocked"

    # One post per vehicle, keyed by slug rather than a (make, model, year) constraint:
    # `model` is nullable and PostgreSQL treats NULLs as distinct, so a unique constraint
    # would let "Toyota, NULL, 1997" in twice. The slug is also the WordPress slug, which
    # is what lets a crashed run find the draft it already created.
    slug = models.SlugField(max_length=255, unique=True)
    make = models.CharField(max_length=255, db_index=True)
    model = models.CharField(max_length=255, null=True, blank=True)
    year = models.PositiveSmallIntegerField(db_index=True)

    # SET_NULL, not CASCADE: deleting an import must not orphan a post that exists on WordPress.
    car_search = models.ForeignKey(
        "searches.CarSearch", on_delete=models.SET_NULL, null=True, blank=True, related_name="blog_posts"
    )
    csv_import = models.ForeignKey(
        "imports.CsvImport", on_delete=models.SET_NULL, null=True, blank=True, related_name="blog_posts"
    )

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Generated copy. `content` is the article body only; the gallery is rendered at publish time.
    title = models.CharField(max_length=255, blank=True, default="")
    content = models.TextField(blank=True, default="")
    seo_title = models.CharField(max_length=255, blank=True, default="")
    seo_description = models.TextField(blank=True, default="")
    seo_keywords = models.TextField(blank=True, default="")
    ai_model = models.CharField(max_length=64, blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)

    wp_post_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    wp_link = models.TextField(null=True, blank=True)
    wp_status = models.CharField(max_length=32, blank=True, default="")
    featured_media_id = models.PositiveIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Digest of the approved images at publish time, so an unchanged post re-runs free.
    images_fingerprint = models.CharField(max_length=64, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="blog_posts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["make", "model", "year"], name="blog_posts_make_model_year_idx"),
            # The chunk runner reads runnable rows in id order.
            models.Index(fields=["status", "id"], name="blog_posts_status_id_idx"),
        ]

    def __str__(self) -> str:
        return " ".join(str(part) for part in (self.year, self.make, self.model) if part)


class BlogPostMedia(models.Model):
    """One WordPress attachment. Its existence is what stops a resumed run re-uploading."""

    blog_post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name="media")
    car_image = models.ForeignKey(
        "images.CarImage", on_delete=models.SET_NULL, null=True, blank=True, related_name="blog_media"
    )
    wp_media_id = models.PositiveIntegerField(db_index=True)
    wp_source_url = models.TextField()
    filename = models.CharField(max_length=255)
    alt_text = models.TextField(blank=True, default="")
    # Commons licences require attribution, so it is carried on the attachment itself.
    caption = models.TextField(blank=True, default="")
    credit_url = models.TextField(blank=True, default="")
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    bytes_uploaded = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["blog_post", "car_image"], name="blog_post_media_post_image_unique")
        ]

    def __str__(self) -> str:
        return f"{self.filename} (wp #{self.wp_media_id})"


class AiUsage(models.Model):
    """
    What one generation cost. Written before the call as a worst-case reservation
    and corrected afterwards, so a crash mid-call over-reports spend rather than
    under-reporting it.
    """

    class Purpose(models.TextChoices):
        POST_CONTENT = "post_content", "Blog post content"

    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"

    blog_post = models.ForeignKey(BlogPost, on_delete=models.SET_NULL, null=True, blank=True, related_name="ai_usages")
    purpose = models.CharField(max_length=32, choices=Purpose.choices, default=Purpose.POST_CONTENT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RESERVED, db_index=True)
    model = models.CharField(max_length=64)

    prompt_tokens = models.PositiveIntegerField(default=0)
    cached_prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # Snapshotted per row: a later price change must not rewrite what past runs cost.
    input_usd_per_1m = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    cached_input_usd_per_1m = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    output_usd_per_1m = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    # Decimal throughout: a budget compared with accumulated float error is not a budget.
    reserved_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))

    request_id = models.CharField(max_length=64, blank=True, default="")
    finish_reason = models.CharField(max_length=32, blank=True, default="")
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["status", "occurred_at"], name="ai_usage_status_time_idx")]

    def __str__(self) -> str:
        return f"{self.model} {self.total_tokens} tok ${self.cost_usd}"


class BudgetPeriod(models.Model):
    """
    The month's running spend, and the row the cap is enforced against.

    It is a cache of the AiUsage rows, held separately so the check is one locked
    read rather than an aggregate over every call ever made.
    """

    month = models.DateField(unique=True)
    spent_usd = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("0"))
    calls = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month"]

    def __str__(self) -> str:
        return f"{self.month:%Y-%m}: ${self.spent_usd}"
