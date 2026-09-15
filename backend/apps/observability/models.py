from django.db import models
from django.utils import timezone


class ErrorEvent(models.Model):
    class Context(models.TextChoices):
        CSV_UPLOAD = "csv_upload", "CSV upload"
        CSV_ROW = "csv_row", "CSV row"
        SEARCH_RUN = "search_run", "Search run"
        IMAGE_DOWNLOAD = "image_download", "Image download"
        WIKIMEDIA_BLOCK = "wikimedia_block", "Wikimedia block"

    class Severity(models.TextChoices):
        ERROR = "error", "Error"
        WARNING = "warning", "Warning"

    context = models.CharField(max_length=32, choices=Context.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.ERROR)
    message = models.TextField(null=True, blank=True)
    exception_class = models.CharField(max_length=255, null=True, blank=True)
    exception_message = models.TextField(null=True, blank=True)
    trace_excerpt = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    car_search = models.ForeignKey(
        "searches.CarSearch", on_delete=models.SET_NULL, null=True, blank=True, related_name="error_events"
    )
    csv_import = models.ForeignKey(
        "imports.CsvImport", on_delete=models.SET_NULL, null=True, blank=True, related_name="error_events"
    )
    car_image = models.ForeignKey(
        "images.CarImage", on_delete=models.SET_NULL, null=True, blank=True, related_name="error_events"
    )
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["context", "occurred_at"], name="error_events_context_time_idx")]

    def __str__(self) -> str:
        return f"[{self.context}] {self.message or self.exception_message or ''}"[:120]
