import time

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Exists, OuterRef
from django.utils.translation import ngettext

from apps.admin_display import admin_link, badge, thumbnail
from apps.images.admin import download_badge, review_badge
from apps.images.models import CarImage
from apps.observability.models import ErrorEvent
from apps.observability.services import error_logger
from apps.searches.models import CarSearch, CommonsCategoryLookup, WikimediaBlockEvent
from apps.searches.services import run_query, search_service
from apps.searches.services.wikimedia import WikimediaBlockedError

STATUS_COLORS = {
    CarSearch.Status.PENDING: "gray",
    CarSearch.Status.RUNNING: "amber",
    CarSearch.Status.COMPLETED: "green",
    CarSearch.Status.FAILED: "red",
}


def search_status_badge(search: CarSearch):
    return badge(search.get_status_display(), STATUS_COLORS.get(search.status, "gray"))


class SourceFilter(admin.SimpleListFilter):
    title = "source"
    parameter_name = "source"

    def lookups(self, request, model_admin):
        return (("csv", "CSV import"), ("adhoc", "Ad-hoc"))

    def queryset(self, request, queryset):
        if self.value() == "csv":
            return queryset.filter(csv_import__isnull=False)
        if self.value() == "adhoc":
            return queryset.filter(csv_import__isnull=True)
        return queryset


class CoverageFilter(admin.SimpleListFilter):
    """What `status` cannot answer: a search that ran and found nothing is still "completed"."""

    title = "coverage"
    parameter_name = "coverage"

    def lookups(self, request, model_admin):
        return (
            ("with_images", "Found images"),
            ("no_images", "Ran, found nothing"),
            ("not_run", "Not run yet"),
        )

    def queryset(self, request, queryset):
        has_images = Exists(CarImage.objects.filter(car_search=OuterRef("pk")))
        match self.value():
            case "with_images":
                return queryset.filter(has_images)
            case "no_images":
                return queryset.filter(~has_images, status=CarSearch.Status.COMPLETED)
            case "not_run":
                return queryset.filter(status__in=[CarSearch.Status.PENDING, CarSearch.Status.RUNNING])
        return queryset


class CarImageInline(admin.TabularInline):
    model = CarImage
    fk_name = "car_search"
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("preview", "year", "title", "make_confirmed", "year_confirmed", "review", "download")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Image")
    def preview(self, obj):
        return thumbnail(obj.thumbnail_url, obj.source_url, height=48)

    @admin.display(description="Review")
    def review(self, obj):
        return review_badge(obj)

    @admin.display(description="Download")
    def download(self, obj):
        return download_badge(obj)


@admin.register(CarSearch)
class CarSearchAdmin(admin.ModelAdmin):
    """Searches are created through the API; the admin inspects and (re-)runs them."""

    list_display = (
        "id",
        "make",
        "model",
        "years",
        "status_badge",
        "images_count",
        "commons_category",
        "source",
        "requested_by",
        "created_at",
    )
    list_display_links = ("id", "make")
    list_filter = ("status", SourceFilter, CoverageFilter, "csv_import")
    list_select_related = ("csv_import", "requested_by")
    search_fields = ("make", "model", "commons_category", "csv_import__original_filename", "requested_by__email")
    date_hierarchy = "created_at"
    list_per_page = 50
    actions = ["run_selected", "refresh_selected"]
    inlines = [CarImageInline]
    fieldsets = (
        (None, {"fields": ("make", "model", "years", "status_badge", "commons_category")}),
        (
            "Filters",
            {"fields": ("color", "transmission", "transparent_background", "images_per_year")},
        ),
        ("Origin", {"fields": ("source", "requested_by", "created_at", "updated_at")}),
    )
    readonly_fields = (
        "make",
        "model",
        "years",
        "status_badge",
        "commons_category",
        "color",
        "transmission",
        "transparent_background",
        "images_per_year",
        "source",
        "requested_by",
        "created_at",
        "updated_at",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(images_count=Count("images"))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_run_permission(self, request):
        opts = self.opts
        return request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    @admin.display(description="Years", ordering="from_year")
    def years(self, obj):
        return str(obj.from_year) if obj.from_year == obj.to_year else f"{obj.from_year}-{obj.to_year}"

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return search_status_badge(obj)

    @admin.display(description="Images", ordering="images_count")
    def images_count(self, obj):
        return obj.images_count

    @admin.display(description="Source", ordering="csv_import")
    def source(self, obj):
        if obj.csv_import_id is None:
            return "Ad-hoc"
        return admin_link(obj.csv_import)

    @admin.action(description="Run selected searches", permissions=["run"])
    def run_selected(self, request, queryset):
        self._run_each(request, queryset, run_query.run_search_query, verb="Ran")

    @admin.action(description="Refresh selected from Wikimedia", permissions=["run"])
    def refresh_selected(self, request, queryset):
        def refresh(search: CarSearch) -> CarSearch:
            try:
                return search_service.refresh_search(search)
            except WikimediaBlockedError:
                raise
            except Exception as exc:
                # run_search_query records its own failures; a refresh does not, so record it here.
                error_logger.record(
                    ErrorEvent.Context.SEARCH_RUN, exc, car_search=search, csv_import=search.csv_import_id
                )
                raise

        self._run_each(request, queryset, refresh, verb="Refreshed")

    def _run_each(self, request, queryset, run, *, verb: str) -> None:
        """Run searches one at a time inside the request, time-boxed like a bulk-run chunk.

        A Wikimedia block stops the loop at once: every further request would be
        refused too, and hammering a blocked API only extends the block.
        """
        limits = settings.CARS_IMAGES
        max_seconds = limits["bulk_run_max_seconds_per_chunk"]
        max_queries = limits["bulk_run_max_queries_per_chunk"]
        searches = list(queryset.order_by("id"))
        started = time.monotonic()
        completed = failed = 0
        blocked: WikimediaBlockedError | None = None

        for search in searches:
            if completed + failed >= max_queries or time.monotonic() - started >= max_seconds:
                break
            try:
                result = run(search)
            except WikimediaBlockedError as exc:
                blocked = exc
                break
            except Exception:
                # Already recorded as an ErrorEvent; keep going with the rest of the selection.
                failed += 1
                continue
            if result.status == CarSearch.Status.FAILED:
                failed += 1
            else:
                completed += 1

        attempted = completed + failed
        not_run = len(searches) - attempted
        summary = ngettext("%(verb)s %(n)d search", "%(verb)s %(n)d searches", attempted) % {
            "verb": verb,
            "n": attempted,
        }
        summary += f": {completed} completed, {failed} failed"
        summary += f", {not_run} not run." if not_run else "."

        if blocked is not None:
            retry = f" Retry after {blocked.retry_after_seconds}s." if blocked.retry_after_seconds else ""
            self.message_user(
                request,
                f"Wikimedia blocked the request (HTTP {blocked.status}), so the run stopped. {summary}{retry}",
                messages.ERROR,
            )
            return
        if not_run:
            summary += " The per-request limit was reached; run the action again to continue."
        self.message_user(request, summary, messages.WARNING if failed or not_run else messages.SUCCESS)


@admin.register(CommonsCategoryLookup)
class CommonsCategoryLookupAdmin(admin.ModelAdmin):
    """Cached make/model → category resolutions. Delete a row to force a fresh lookup."""

    list_display = ("make", "model", "category_display", "checked_at")
    list_filter = (("category", admin.EmptyFieldListFilter), "checked_at")
    search_fields = ("make", "model", "category")
    readonly_fields = ("make", "model", "category", "checked_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Category", ordering="category")
    def category_display(self, obj):
        return obj.category or badge("miss", "gray")


@admin.register(WikimediaBlockEvent)
class WikimediaBlockEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "status_code", "retry_after_seconds", "search_link", "import_link")
    list_filter = ("status_code",)
    list_select_related = ("car_search", "csv_import")
    date_hierarchy = "occurred_at"
    readonly_fields = (
        "occurred_at",
        "status_code",
        "retry_after_seconds",
        "search_link",
        "import_link",
        "response_excerpt",
    )
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Search")
    def search_link(self, obj):
        return admin_link(obj.car_search)

    @admin.display(description="CSV import")
    def import_link(self, obj):
        return admin_link(obj.csv_import)
