"""
Resource shapes (ports of app/Http/Resources/Api/V1) and request validation
(ports of app/Http/Requests/Api/V1). Field lists and their order mirror the
mobile client's Zod schemas.
"""

from typing import Any

from django.conf import settings
from rest_framework import serializers

from api.v1.filters import MIN_YEAR, max_year
from apps.accounts import abilities
from apps.accounts.models import User
from apps.images.models import CarImage
from apps.imports.models import CsvImport
from apps.observability.models import ErrorEvent
from apps.searches.models import CarSearch

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name", "email"]
        read_only_fields = fields


class ImageSerializer(serializers.ModelSerializer):
    car_search_id = serializers.IntegerField(read_only=True)
    reviewed_by = serializers.IntegerField(source="reviewed_by_id", read_only=True)

    class Meta:
        model = CarImage
        fields = [
            "id",
            "car_search_id",
            "make",
            "model",
            "year",
            "color",
            "title",
            "description",
            "source_url",
            "thumbnail_url",
            "width",
            "height",
            "license",
            "attribution",
            "make_confirmed",
            "year_confirmed",
            "review_status",
            "reviewed_by",
            "reviewed_at",
            "download_status",
            "created_at",
        ]
        read_only_fields = fields


class SearchSerializer(serializers.ModelSerializer):
    """`images_count` needs the queryset annotated with Count("images")."""

    csv_import_id = serializers.IntegerField(read_only=True)
    requested_by = serializers.IntegerField(source="requested_by_id", read_only=True)
    images_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CarSearch
        fields = [
            "id",
            "make",
            "model",
            "commons_category",
            "from_year",
            "to_year",
            "color",
            "transmission",
            "transparent_background",
            "images_per_year",
            "status",
            "csv_import_id",
            "requested_by",
            "images_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SearchWithImagesSerializer(SearchSerializer):
    """The create response: the only one that embeds the harvested images."""

    images = ImageSerializer(many=True, read_only=True)

    class Meta(SearchSerializer.Meta):
        fields = [*SearchSerializer.Meta.fields[:-2], "images", "created_at", "updated_at"]
        read_only_fields = fields


class ImportSerializer(serializers.ModelSerializer):
    """
    `importer_name` rather than a nested user, so the list never carries an
    email. Needs select_related("imported_by") and Count("searches").
    """

    imported_by = serializers.IntegerField(source="imported_by_id", read_only=True)
    importer_name = serializers.CharField(source="imported_by.name", read_only=True)
    searches_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CsvImport
        fields = [
            "id",
            "original_filename",
            "total_rows",
            "unique_combos",
            "duplicates_skipped",
            "imported_by",
            "importer_name",
            "searches_count",
            "created_at",
        ]
        read_only_fields = fields


class ImportDetailSerializer(ImportSerializer):
    """Adds `coverage` (null for an import with no searches), from context."""

    coverage = serializers.SerializerMethodField()

    class Meta(ImportSerializer.Meta):
        fields = [*ImportSerializer.Meta.fields[:-1], "coverage", "created_at"]
        read_only_fields = fields

    def get_coverage(self, instance: CsvImport) -> dict[str, int] | None:
        return self.context["coverage"]


class ErrorEventSerializer(serializers.ModelSerializer):
    car_search_id = serializers.IntegerField(read_only=True)
    csv_import_id = serializers.IntegerField(read_only=True)
    car_image_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ErrorEvent
        fields = [
            "id",
            "context",
            "severity",
            "message",
            "exception_class",
            "exception_message",
            "trace_excerpt",
            "details",
            "car_search_id",
            "csv_import_id",
            "car_image_id",
            "occurred_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class StrictBooleanField(serializers.BooleanField):
    """true/false/1/0 only; DRF's default also takes "yes", "on", "t"..."""

    TRUE_VALUES = {True, "1", "true"}
    FALSE_VALUES = {False, "0", "false"}
    NULL_VALUES: set = set()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
    # Names the token ("Pixel 8") so one device can be revoked alone.
    device_name = serializers.CharField(max_length=255)
    # Narrowing only; `min_length=1` because a zero-ability token 403s everywhere.
    abilities = serializers.ListField(
        child=serializers.ChoiceField(choices=abilities.ALL), min_length=1, required=False
    )


class ReviewSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(choices=CarImage.ReviewStatus.choices)


class NullableText(serializers.CharField):
    """An optional string where "" means null, as Laravel's ConvertEmptyStringsToNull made it."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(required=False, allow_null=True, allow_blank=True, default=None, **kwargs)

    def run_validation(self, data: Any = serializers.empty) -> str | None:
        return super().run_validation(data) or None


class SearchCreateSerializer(serializers.Serializer):
    """The admin form's rules plus the API caps, which keep an inline run short."""

    make = serializers.CharField(max_length=255)
    model = NullableText(max_length=255)
    from_year = serializers.IntegerField()
    to_year = serializers.IntegerField()
    color = NullableText(max_length=64)
    transmission = NullableText(max_length=64)
    transparent_background = StrictBooleanField(required=False, default=False)
    images_per_year = serializers.IntegerField(required=False)

    def get_fields(self) -> dict[str, serializers.Field]:
        """Bounds read at request time: the year rolls over, and the cap is config."""
        fields = super().get_fields()
        cap = settings.CARS_IMAGES["api_search_max_images_per_year"]
        fields["from_year"] = serializers.IntegerField(min_value=MIN_YEAR, max_value=max_year())
        fields["to_year"] = serializers.IntegerField(min_value=MIN_YEAR, max_value=max_year())
        fields["images_per_year"] = serializers.IntegerField(min_value=1, max_value=cap, default=cap)
        return fields

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        span = settings.CARS_IMAGES["api_search_max_year_span"]
        if abs(attrs["to_year"] - attrs["from_year"]) > span:
            raise serializers.ValidationError(
                {
                    "to_year": f"The year range may span at most {span} years, "
                    "because the search runs inside this request."
                }
            )
        # Ascending, so dedupe and creation see the same key.
        if attrs["from_year"] > attrs["to_year"]:
            attrs["from_year"], attrs["to_year"] = attrs["to_year"], attrs["from_year"]
        return attrs


class RunChunkSerializer(serializers.Serializer):
    csv_import_id = serializers.PrimaryKeyRelatedField(queryset=CsvImport.objects.all())


class ImportUploadSerializer(serializers.Serializer):
    MIME_TYPES = ("text/csv", "text/plain", "application/csv", "application/vnd.ms-excel")

    csv_file = serializers.FileField()

    def validate_csv_file(self, upload):
        max_kb = settings.CARS_IMAGES["csv_import_max_upload_kb"]
        if upload.size > max_kb * 1024:
            raise serializers.ValidationError(f"The csv file field must not be greater than {max_kb} kilobytes.")
        # Sniffed, not trusted from the client's Content-Type: a CSV is text.
        head = upload.read(8192)
        upload.seek(0)
        if b"\x00" in head:
            raise serializers.ValidationError(
                f"The csv file field must be a file of type: {', '.join(self.MIME_TYPES)}."
            )
        return upload


class ExportFormatSerializer(serializers.Serializer):
    """The format half of an export request; the filters are ImageFilter's."""

    format = serializers.ChoiceField(choices=[("csv", "csv"), ("zip", "zip")])
