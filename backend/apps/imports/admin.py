from django.contrib import admin
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html, format_html_join

from apps.admin_display import changelist_url
from apps.imports.models import CsvImport
from apps.imports.services import coverage
from apps.searches.admin import search_status_badge
from apps.searches.models import CarSearch

INLINE_SEARCH_LIMIT = 100


class _FirstSearchesFormSet(BaseInlineFormSet):
    """An import can hold 1,000 searches; render the first page and link to the rest."""

    def get_queryset(self):
        if not hasattr(self, "_limited_queryset"):
            self._limited_queryset = super().get_queryset()[:INLINE_SEARCH_LIMIT]
        return self._limited_queryset


class CarSearchInline(admin.TabularInline):
    model = CarSearch
    fk_name = "csv_import"
    formset = _FirstSearchesFormSet
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("from_year", "make", "model", "status_badge", "images_count", "commons_category")
    readonly_fields = fields
    ordering = ("id",)
    verbose_name_plural = f"Searches (first {INLINE_SEARCH_LIMIT})"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(images_count=Count("images"))

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Status")
    def status_badge(self, obj):
        return search_status_badge(obj)

    @admin.display(description="Images")
    def images_count(self, obj):
        return obj.images_count


@admin.register(CsvImport)
class CsvImportAdmin(admin.ModelAdmin):
    """Imports are uploaded through the API. Deleting one removes its searches and their images."""

    list_display = (
        "id",
        "original_filename",
        "total_rows",
        "unique_combos",
        "duplicates_skipped",
        "imported_by",
        "created_at",
    )
    list_display_links = ("id", "original_filename")
    list_select_related = ("imported_by",)
    search_fields = ("original_filename", "imported_by__email", "imported_by__name")
    date_hierarchy = "created_at"
    inlines = [CarSearchInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "original_filename",
                    "total_rows",
                    "unique_combos",
                    "duplicates_skipped",
                    "imported_by",
                    "created_at",
                )
            },
        ),
        ("Coverage", {"fields": ("coverage_report", "searches_link")}),
    )
    readonly_fields = (
        "original_filename",
        "total_rows",
        "unique_combos",
        "duplicates_skipped",
        "imported_by",
        "created_at",
        "coverage_report",
        "searches_link",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Coverage")
    def coverage_report(self, obj):
        report = coverage.import_coverage(obj.pk)
        if report is None:
            return "This import has no searches."

        base = {"csv_import__id__exact": obj.pk}
        rows = (
            ("Total", report["total"], base),
            ("Searched", report["searched"], None),
            ("Not run", report["not_run"], {**base, "coverage": "not_run"}),
            ("Failed", report["failed"], {**base, "status__exact": CarSearch.Status.FAILED}),
            ("With images", report["with_images"], {**base, "coverage": "with_images"}),
            ("No images", report["no_images"], {**base, "coverage": "no_images"}),
        )
        cells = format_html_join(
            "",
            "<tr><th scope='row' style='padding-right:1.5em'>{}</th><td>{}</td></tr>",
            (
                (label, format_html('<a href="{}">{}</a>', changelist_url("searches", "carsearch", **params), value))
                if params
                else (label, value)
                for label, value, params in rows
            ),
        )
        return format_html("<table>{}</table>", cells)

    @admin.display(description="Searches")
    def searches_link(self, obj):
        url = changelist_url("searches", "carsearch", csv_import__id__exact=obj.pk)
        return format_html('<a href="{}">Open all searches for this import</a>', url)
