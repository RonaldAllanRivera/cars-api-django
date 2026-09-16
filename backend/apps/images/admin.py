import csv
import os
import tempfile

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.translation import ngettext

from apps.admin_display import admin_link, badge, thumbnail
from apps.exports.services import csv_exporter, zip_builder
from apps.images.models import CarImage
from apps.publishing.services.seeding import sync_posts

REVIEW_COLORS = {
    CarImage.ReviewStatus.PENDING: "gray",
    CarImage.ReviewStatus.APPROVED: "green",
    CarImage.ReviewStatus.REJECTED: "red",
}

DOWNLOAD_COLORS = {
    CarImage.DownloadStatus.NOT_DOWNLOADED: "gray",
    CarImage.DownloadStatus.DOWNLOADING: "amber",
    CarImage.DownloadStatus.DOWNLOADED: "green",
    CarImage.DownloadStatus.FAILED: "red",
}


def review_badge(image: CarImage):
    return badge(image.get_review_status_display(), REVIEW_COLORS.get(image.review_status, "gray"))


def download_badge(image: CarImage):
    return badge(image.get_download_status_display(), DOWNLOAD_COLORS.get(image.download_status, "gray"))


class _Echo:
    """File-like object whose write() returns the line, for streaming csv.writer output."""

    def write(self, value):
        return value


@admin.register(CarImage)
class CarImageAdmin(admin.ModelAdmin):
    list_display = (
        "preview",
        "title_short",
        "make",
        "model",
        "year",
        "make_confirmed",
        "year_confirmed",
        "review",
        "download",
        "search_link",
    )
    list_display_links = ("title_short",)
    list_filter = ("review_status", "download_status", "make_confirmed", "year_confirmed", "make", "provider")
    list_select_related = ("car_search",)
    search_fields = ("title", "make", "model", "provider_image_id")
    list_per_page = 50
    actions = [
        "approve_selected",
        "reject_selected",
        "reset_selected",
        "download_zip",
        "export_csv",
        "queue_blog_posts",
    ]
    fieldsets = (
        (None, {"fields": ("preview_large", "title", "description", "source_link")}),
        ("Vehicle", {"fields": ("make", "model", "year", "color", "make_confirmed", "year_confirmed")}),
        ("Review", {"fields": ("review_status", "reviewed_by", "reviewed_at")}),
        (
            "Source",
            {
                "fields": (
                    "search_link",
                    "provider",
                    "provider_image_id",
                    "width",
                    "height",
                    "license",
                    "attribution",
                    "download_status",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    # Everything but the review decision is harvested data and stays read-only.
    readonly_fields = (
        "preview_large",
        "title",
        "description",
        "source_link",
        "make",
        "model",
        "year",
        "color",
        "make_confirmed",
        "year_confirmed",
        "reviewed_by",
        "reviewed_at",
        "search_link",
        "provider",
        "provider_image_id",
        "width",
        "height",
        "license",
        "attribution",
        "download_status",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "review_status" in form.changed_data:
            self._stamp_review(obj, request.user)
        super().save_model(request, obj, form, change)

    @staticmethod
    def _stamp_review(obj: CarImage, user) -> None:
        if obj.review_status == CarImage.ReviewStatus.PENDING:
            obj.reviewed_by, obj.reviewed_at = None, None
        else:
            obj.reviewed_by, obj.reviewed_at = user, timezone.now()

    # -- columns -----------------------------------------------------------

    @admin.display(description="Image")
    def preview(self, obj):
        return thumbnail(obj.thumbnail_url, obj.source_url)

    @admin.display(description="Preview")
    def preview_large(self, obj):
        return thumbnail(obj.thumbnail_url, obj.source_url, height=240)

    @admin.display(description="Title", ordering="title")
    def title_short(self, obj):
        return obj.title if len(obj.title) <= 60 else f"{obj.title[:57]}…"

    @admin.display(description="Original")
    def source_link(self, obj):
        return thumbnail(None, obj.source_url)

    @admin.display(description="Review", ordering="review_status")
    def review(self, obj):
        return review_badge(obj)

    @admin.display(description="Download", ordering="download_status")
    def download(self, obj):
        return download_badge(obj)

    @admin.display(description="Search")
    def search_link(self, obj):
        return admin_link(obj.car_search, f"#{obj.car_search_id}" if obj.car_search_id else None)

    # -- review actions ----------------------------------------------------

    def _review(self, request, queryset, status: str) -> None:
        if status == CarImage.ReviewStatus.PENDING:
            fields = {"reviewed_by": None, "reviewed_at": None}
        else:
            fields = {"reviewed_by": request.user, "reviewed_at": timezone.now()}
        updated = queryset.update(review_status=status, updated_at=timezone.now(), **fields)
        label = CarImage.ReviewStatus(status).label.lower()
        self.message_user(
            request,
            ngettext("Marked %(n)d image as %(label)s.", "Marked %(n)d images as %(label)s.", updated)
            % {"n": updated, "label": label},
            messages.SUCCESS,
        )

    @admin.action(description="Approve selected images", permissions=["change"])
    def approve_selected(self, request, queryset):
        self._review(request, queryset, CarImage.ReviewStatus.APPROVED)

    @admin.action(description="Reject selected images", permissions=["change"])
    def reject_selected(self, request, queryset):
        self._review(request, queryset, CarImage.ReviewStatus.REJECTED)

    @admin.action(description="Reset selected to pending", permissions=["change"])
    def reset_selected(self, request, queryset):
        self._review(request, queryset, CarImage.ReviewStatus.PENDING)

    # -- publishing ---------------------------------------------------------

    @admin.action(description="Queue blog posts for approved images in selection", permissions=["change"])
    def queue_blog_posts(self, request, queryset):
        """Queues one post per vehicle; spends nothing until the posts are published."""
        result = sync_posts(queryset, requested_by=request.user)
        self.message_user(
            request,
            f"Queued {result.created} new blog post(s); {result.existing} already queued. Only approved images count.",
            messages.SUCCESS,
        )

    # -- export actions ----------------------------------------------------

    @admin.action(description="Download selected as ZIP", permissions=["view"])
    def download_zip(self, request, queryset):
        limit = settings.CARS_IMAGES["bulk_download_max_images"]
        selected = queryset.count()
        if selected > limit:
            self.message_user(
                request,
                f"Select at most {limit} images per ZIP ({selected} selected). Each image is downloaded "
                "and resized inside this request.",
                messages.ERROR,
            )
            return None

        fd, path = tempfile.mkstemp(prefix="car-images-", suffix=".zip")
        os.close(fd)
        try:
            added = zip_builder.build_zip_to_file(queryset.select_related("car_search").order_by("id"), path)
            if added == 0:
                self.message_user(
                    request,
                    "None of the selected images could be downloaded, so no ZIP was produced. "
                    "See the error log for details.",
                    messages.ERROR,
                )
                return None
            handle = open(path, "rb")  # noqa: SIM115 - FileResponse closes it
        finally:
            # Unlinking an open file is safe on POSIX: the handle keeps the data readable
            # until FileResponse closes it, and nothing is left behind on disk if the
            # client disconnects mid-download.
            os.unlink(path)

        return FileResponse(handle, as_attachment=True, filename=f"car-images-{_timestamp()}.zip")

    @admin.action(description="Export selected as CSV", permissions=["view"])
    def export_csv(self, request, queryset):
        writer = csv.writer(_Echo())
        rows = csv_exporter.export_rows(queryset.select_related("car_search").order_by("id").iterator())
        response = StreamingHttpResponse((writer.writerow(row) for row in rows), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="car-images-{_timestamp()}.csv"'
        return response


def _timestamp() -> str:
    return timezone.now().strftime("%Y%m%d-%H%M%S")
