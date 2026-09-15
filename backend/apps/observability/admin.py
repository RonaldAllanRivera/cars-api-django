import json

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.translation import ngettext

from apps.admin_display import admin_link, badge
from apps.observability.models import ErrorEvent
from apps.observability.services import pruning

CONTEXT_COLORS = {
    ErrorEvent.Context.WIKIMEDIA_BLOCK: "red",
    ErrorEvent.Context.CSV_ROW: "amber",
    ErrorEvent.Context.CSV_UPLOAD: "blue",
}

PRE_STYLE = "white-space:pre-wrap;word-break:break-word;max-height:32em;overflow:auto;margin:0"


@admin.register(ErrorEvent)
class ErrorEventAdmin(admin.ModelAdmin):
    """Read-only pipeline error log, with a prune button in place of a cron job."""

    list_display = ("occurred_at", "context_badge", "severity_badge", "message_short", "related")
    list_display_links = ("occurred_at",)
    list_filter = ("context", "severity", "csv_import")
    list_select_related = ("car_search", "csv_import", "car_image")
    search_fields = ("message", "exception_class", "exception_message")
    date_hierarchy = "occurred_at"
    list_per_page = 50
    fieldsets = (
        ("What happened", {"fields": ("occurred_at", "context_badge", "severity_badge", "message")}),
        ("Related", {"fields": ("search_link", "import_link", "image_link")}),
        ("Exception", {"fields": ("exception_class", "exception_message", "trace"), "classes": ("collapse",)}),
        ("Details", {"fields": ("details_json",)}),
    )
    readonly_fields = (
        "occurred_at",
        "context_badge",
        "severity_badge",
        "message",
        "search_link",
        "import_link",
        "image_link",
        "exception_class",
        "exception_message",
        "trace",
        "details_json",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # -- prune -------------------------------------------------------------

    def get_urls(self):
        opts = self.opts
        return [
            path(
                "prune/",
                self.admin_site.admin_view(self.prune_view),
                name=f"{opts.app_label}_{opts.model_name}_prune",
            ),
            *super().get_urls(),
        ]

    def changelist_view(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "has_prune_permission": self.has_delete_permission(request)}
        return super().changelist_view(request, extra_context)

    def prune_view(self, request):
        if not self.has_delete_permission(request):
            raise PermissionDenied
        changelist = f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"

        if request.method == "POST":
            deleted = pruning.prune()
            self.message_user(
                request,
                ngettext("Pruned %d error event.", "Pruned %d error events.", deleted) % deleted,
                messages.SUCCESS,
            )
            return redirect(changelist)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": "Prune old error events",
            "retention_days": pruning.retention_days(),
            "prunable": pruning.prunable_count(),
        }
        return TemplateResponse(request, "admin/observability/errorevent/prune_confirmation.html", context)

    # -- columns -----------------------------------------------------------

    @admin.display(description="Context", ordering="context")
    def context_badge(self, obj):
        return badge(obj.get_context_display(), CONTEXT_COLORS.get(obj.context, "gray"))

    @admin.display(description="Severity", ordering="severity")
    def severity_badge(self, obj):
        return badge(obj.get_severity_display(), "red" if obj.severity == ErrorEvent.Severity.ERROR else "amber")

    @admin.display(description="Message")
    def message_short(self, obj):
        text = obj.message or obj.exception_message or ""
        return text if len(text) <= 120 else f"{text[:117]}…"

    @admin.display(description="Related")
    def related(self, obj):
        """The most specific record the failure was about."""
        if obj.car_image_id:
            return admin_link(obj.car_image, f"Image #{obj.car_image_id}")
        if obj.car_search_id:
            return admin_link(obj.car_search)
        if obj.csv_import_id:
            return admin_link(obj.csv_import)
        return "—"

    @admin.display(description="Search")
    def search_link(self, obj):
        return admin_link(obj.car_search)

    @admin.display(description="CSV import")
    def import_link(self, obj):
        return admin_link(obj.csv_import)

    @admin.display(description="Image")
    def image_link(self, obj):
        return admin_link(obj.car_image, f"Image #{obj.car_image_id}" if obj.car_image_id else None)

    @admin.display(description="Trace")
    def trace(self, obj):
        if not obj.trace_excerpt:
            return "—"
        return format_html('<pre style="{}">{}</pre>', PRE_STYLE, obj.trace_excerpt)

    @admin.display(description="Details")
    def details_json(self, obj):
        if not obj.details:
            return "—"
        pretty = json.dumps(obj.details, indent=2, sort_keys=True, ensure_ascii=False)
        return format_html('<pre style="{}">{}</pre>', PRE_STYLE, pretty)
