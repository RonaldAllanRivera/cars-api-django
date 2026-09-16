"""
Query filters for the list endpoints.

Every filter is optional, but one that is sent must be valid: `?make=` or
`?make_confirmed=yes` is a 422, never a silently ignored filter.
"""

from typing import Any

import django_filters
from django import forms
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch

MIN_YEAR = 1900


def max_year() -> int:
    """Next year: a model year can run ahead of the calendar."""
    return timezone.now().year + 1


class VerdictField(forms.Field):
    """
    A strict boolean: true/false/1/0 (strings from a query, or JSON values).
    Django's own boolean fields also accept "yes", "on" and blank.
    """

    default_error_messages = {"invalid": "Must be true, false, 1 or 0."}
    TRUE = ("true", "1")
    FALSE = ("false", "0")

    def to_python(self, value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in self.TRUE:
            return True
        if text in self.FALSE:
            return False
        raise forms.ValidationError(self.error_messages["invalid"], code="invalid")


class VerdictFilter(django_filters.Filter):
    """Matches its value only: the nullable "not evaluated" verdict never matches."""

    field_class = VerdictField


class IntegerFilter(django_filters.NumberFilter):
    field_class = forms.IntegerField


class StrictFilterSet(django_filters.FilterSet):
    """A FilterSet whose sent-but-blank parameters are errors rather than no-ops."""

    def get_form_class(self) -> type[forms.Form]:
        base = super().get_form_class()
        data = self.data

        class StrictForm(base):
            def clean(self) -> dict:
                cleaned = super().clean()
                for name in self.fields:
                    if name in data and data.get(name) in ("", None) and name not in self.errors:
                        self.add_error(name, "This field may not be blank.")
                return cleaned

        return StrictForm

    def validated_params(self) -> dict[str, str]:
        """The sent filters, normalised to query-string values (for a signed export link)."""
        params: dict[str, str] = {}
        for name, value in self.form.cleaned_data.items():
            if name not in self.data or value is None:
                continue
            if isinstance(value, bool):
                params[name] = "1" if value else "0"
            else:
                params[name] = str(getattr(value, "pk", value))
        return params


class ImageFilter(StrictFilterSet):
    """Shared by /images, /images/count, /searches/{id}/images and exports."""

    make = django_filters.CharFilter(max_length=255)
    model = django_filters.CharFilter(max_length=255)
    year = IntegerFilter(min_value=MIN_YEAR)
    make_confirmed = VerdictFilter()
    year_confirmed = VerdictFilter()
    review_status = django_filters.ChoiceFilter(choices=CarImage.ReviewStatus.choices)
    download_status = django_filters.ChoiceFilter(choices=CarImage.DownloadStatus.choices)
    # Through the search: an image belongs to a search, the search to an import.
    csv_import_id = django_filters.ModelChoiceFilter(
        field_name="car_search__csv_import", queryset=CsvImport.objects.all()
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.filters["year"].extra["max_value"] = max_year()


class SearchFilter(StrictFilterSet):
    status = django_filters.ChoiceFilter(choices=CarSearch.Status.choices)
    source = django_filters.ChoiceFilter(choices=[("csv", "csv"), ("adhoc", "adhoc")], method="filter_source")
    csv_import_id = django_filters.ModelChoiceFilter(field_name="csv_import", queryset=CsvImport.objects.all())
    coverage = django_filters.ChoiceFilter(
        choices=[("with_images", "with_images"), ("no_images", "no_images"), ("not_run", "not_run")],
        method="filter_coverage",
    )

    def filter_source(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        return queryset.filter(csv_import__isnull=value == "adhoc")

    def filter_coverage(self, queryset: QuerySet, name: str, value: str) -> QuerySet:
        """
        What `status` cannot say: a search that ran and found nothing is
        `completed`, like one that found five. `running` counts as not run -
        with no worker, a row left running is a request that died mid-search.
        """
        has_images = Exists(CarImage.objects.filter(car_search=OuterRef("pk")))
        if value == "with_images":
            return queryset.filter(has_images)
        if value == "no_images":
            return queryset.filter(~has_images, status=CarSearch.Status.COMPLETED)
        return queryset.filter(status__in=[CarSearch.Status.PENDING, CarSearch.Status.RUNNING])


class ErrorFilter(StrictFilterSet):
    context = django_filters.ChoiceFilter(choices=ErrorEvent.Context.choices)
    severity = django_filters.ChoiceFilter(choices=ErrorEvent.Severity.choices)
