"""
Admin for AI-written blog posts and the spend behind them.

Everything harvested is read-only. Actions are named for what they cost:
publishing may spend AI budget, updating never does, and rewriting only
discards text so the next publish pays for it again.
"""

from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from apps.admin_display import admin_link, badge, thumbnail
from apps.publishing.models import AiUsage, BlogPost, BlogPostMedia, BudgetPeriod
from apps.publishing.services import budget, media, publish, wordpress
from apps.publishing.services.run_chunk import run_chunk

POST_STATUS_COLORS = {
    BlogPost.Status.PENDING: "gray",
    BlogPost.Status.GENERATING: "blue",
    BlogPost.Status.GENERATED: "blue",
    BlogPost.Status.PUBLISHING: "blue",
    BlogPost.Status.PUBLISHED: "green",
    BlogPost.Status.FAILED: "red",
    BlogPost.Status.BLOCKED: "amber",
}
USAGE_STATUS_COLORS = {
    AiUsage.Status.RESERVED: "blue",
    AiUsage.Status.SUCCEEDED: "green",
    AiUsage.Status.FAILED: "red",
    AiUsage.Status.ABANDONED: "amber",
}
MONEY = DecimalField(max_digits=12, decimal_places=6)


class _ReadOnly:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class BlogPostMediaInline(_ReadOnly, admin.TabularInline):
    model = BlogPostMedia
    extra = 0
    can_delete = False
    fields = ("position", "preview", "is_featured", "wp_media_id", "filename", "caption")
    readonly_fields = fields

    @admin.display(description="Image")
    def preview(self, obj):
        return thumbnail(obj.wp_source_url, obj.wp_source_url, height=48)


@admin.register(BlogPost)
class BlogPostAdmin(_ReadOnly, admin.ModelAdmin):
    list_display = ("id", "vehicle", "status_badge", "images_count", "ai_cost", "wordpress", "attempts", "created_at")
    list_display_links = ("id", "vehicle")
    list_filter = ("status", "year", "csv_import")
    list_select_related = ("csv_import",)
    search_fields = ("make", "model", "slug", "title", "=wp_post_id")
    date_hierarchy = "created_at"
    list_per_page = 50
    actions = ["publish_selected", "update_on_wordpress", "rewrite_selected"]
    inlines = [BlogPostMediaInline]
    fieldsets = (
        ("Vehicle", {"fields": ("vehicle", "slug", "status_badge", "search_link", "import_link", "requested_by")}),
        ("Article", {"fields": ("title", "article")}),
        ("SEO", {"fields": ("seo_title", "seo_description", "seo_keywords")}),
        ("WordPress", {"fields": ("wordpress", "wp_status", "featured_media_id", "published_at")}),
        ("Cost and run state", {"fields": ("ai_model", "ai_cost", "generated_at", "attempts", "last_error")}),
    )
    readonly_fields = (
        "vehicle",
        "slug",
        "status_badge",
        "search_link",
        "import_link",
        "requested_by",
        "title",
        "article",
        "seo_title",
        "seo_description",
        "seo_keywords",
        "wordpress",
        "wp_status",
        "featured_media_id",
        "published_at",
        "ai_model",
        "ai_cost",
        "generated_at",
        "attempts",
        "last_error",
    )

    def get_queryset(self, request):
        # A subquery, not Sum over a join: joined to its media rows the cost would be counted once per image.
        spent = (
            AiUsage.objects.filter(blog_post=OuterRef("pk"))
            .values("blog_post")
            .annotate(total=Sum("cost_usd"))
            .values("total")
        )
        media_count = BlogPostMedia.objects.filter(blog_post=OuterRef("pk")).values("blog_post")
        return (
            super()
            .get_queryset(request)
            .annotate(
                ai_cost_total=Coalesce(Subquery(spent, output_field=MONEY), Value(Decimal("0")), output_field=MONEY),
                images_total=Coalesce(Subquery(media_count.annotate(n=Count("pk")).values("n")), Value(0)),
            )
        )

    def has_run_permission(self, request):
        # Change permission, as for running searches: publishing spends money and writes to WordPress.
        opts = self.opts
        return request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    @admin.display(description="Vehicle", ordering="make")
    def vehicle(self, obj):
        return str(obj)

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.get_status_display(), POST_STATUS_COLORS.get(obj.status, "gray"))

    @admin.display(description="Images", ordering="images_total")
    def images_count(self, obj):
        return getattr(obj, "images_total", None)

    @admin.display(description="AI cost", ordering="ai_cost_total")
    def ai_cost(self, obj):
        total = getattr(obj, "ai_cost_total", None)
        return "—" if total is None else f"${total:.4f}"

    @admin.display(description="WordPress", ordering="wp_post_id")
    def wordpress(self, obj):
        if not obj.wp_post_id:
            return "—"
        if obj.wp_link:
            return format_html('<a href="{}" target="_blank" rel="noopener">#{}</a>', obj.wp_link, obj.wp_post_id)
        return f"#{obj.wp_post_id}"

    @admin.display(description="Search")
    def search_link(self, obj):
        return admin_link(obj.car_search)

    @admin.display(description="Import")
    def import_link(self, obj):
        return admin_link(obj.csv_import)

    @admin.display(description="Article")
    def article(self, obj):
        return format_html('<pre style="white-space:pre-wrap;max-height:30em;overflow:auto">{}</pre>', obj.content)

    @admin.action(description="Write and publish selected as drafts (spends AI budget)", permissions=["run"])
    def publish_selected(self, request, queryset):
        result = run_chunk(post_ids=list(queryset.order_by("id").values_list("pk", flat=True)))
        counts = Counter(outcome.outcome for outcome in result.outcomes)
        summary = ", ".join(f"{count} {outcome}" for outcome, count in sorted(counts.items())) or "nothing to do"
        summary = f"{summary}. AI spend this month: ${Decimal(result.spent_usd):.2f}."
        if result.blocked:
            self.message_user(
                request, f"Stopped ({result.blocked.reason}): {result.blocked.message} {summary}", messages.ERROR
            )
            return
        if result.remaining:
            summary += (
                f" {result.remaining} selected post(s) remain; the per-request limit was reached,"
                " so run the action again."
            )
        level = messages.WARNING if counts.get("failed") or result.remaining else messages.SUCCESS
        self.message_user(request, summary, level)

    @admin.action(description="Update selected on WordPress (no AI spend)", permissions=["run"])
    def update_on_wordpress(self, request, queryset):
        """Re-uploads missing images and re-sends posts that already have their text; never writes new text."""
        limit = settings.CARS_PUBLISHING["max_posts_per_chunk"]
        written = list(queryset.filter(generated_at__isnull=False).exclude(content="").order_by("id"))
        skipped = queryset.count() - len(written)
        counts: Counter = Counter()
        try:
            with wordpress.client() as wp, media.fetch_client() as fetcher:
                for post in written[:limit]:
                    try:
                        counts[publish.generate_and_publish(post, wp=wp, fetcher=fetcher).outcome] += 1
                    except wordpress.WordPressBlockedError:
                        raise
                    except Exception:
                        counts["failed"] += 1
        except wordpress.WordPressError as error:
            self.message_user(request, f"WordPress refused the request: {error}", messages.ERROR)
            return
        parts = [f"{count} {outcome}" for outcome, count in sorted(counts.items())]
        parts.append(f"{skipped} skipped (no text yet)")
        leftover = max(len(written) - limit, 0)
        if leftover:
            parts.append(f"{leftover} left for the next run")
        self.message_user(
            request, ", ".join(parts) + ".", messages.WARNING if counts["failed"] or leftover else messages.SUCCESS
        )

    @admin.action(
        description="Discard text of selected so it is rewritten (next publish spends AI budget)", permissions=["run"]
    )
    def rewrite_selected(self, request, queryset):
        # The WordPress id is kept, so the rewrite updates the same post instead of creating a second one.
        count = queryset.update(
            title="",
            content="",
            seo_title="",
            seo_description="",
            seo_keywords="",
            generated_at=None,
            attempts=0,
            status=BlogPost.Status.PENDING,
            last_error=None,
        )
        self.message_user(
            request, f"Discarded the text of {count} post(s); publish them to write it again.", messages.SUCCESS
        )


@admin.register(AiUsage)
class AiUsageAdmin(_ReadOnly, admin.ModelAdmin):
    """The ledger the monthly budget is built from, so rows can be read but never deleted."""

    list_display = ("id", "occurred_at", "model", "status_badge", "post_link", "input_tokens", "output_tokens", "cost")
    list_filter = ("status", "model")
    list_select_related = ("blog_post",)
    date_hierarchy = "occurred_at"
    readonly_fields = [field.name for field in AiUsage._meta.fields]

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return badge(obj.get_status_display(), USAGE_STATUS_COLORS.get(obj.status, "gray"))

    @admin.display(description="Post")
    def post_link(self, obj):
        return admin_link(obj.blog_post)

    @admin.display(description="Cost", ordering="cost_usd")
    def cost(self, obj):
        return f"${obj.cost_usd:.6f}"


@admin.register(BudgetPeriod)
class BudgetPeriodAdmin(_ReadOnly, admin.ModelAdmin):
    list_display = ("month", "spent", "calls", "updated_at")
    readonly_fields = ("month", "spent_usd", "calls", "created_at", "updated_at")
    actions = ["recompute_selected"]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_run_permission(self, request):
        return request.user.has_perm("publishing.change_budgetperiod")

    @admin.display(description="Spent", ordering="spent_usd")
    def spent(self, obj):
        return f"${obj.spent_usd:.4f}"

    @admin.action(description="Recompute selected months from AI usage", permissions=["run"])
    def recompute_selected(self, request, queryset):
        months = [budget.recompute_period(period.month) for period in queryset]
        self.message_user(request, f"Recomputed {len(months)} month(s) from their AI usage rows.", messages.SUCCESS)
