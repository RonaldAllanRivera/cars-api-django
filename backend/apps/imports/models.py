from django.conf import settings
from django.db import models


class CsvImport(models.Model):
    original_filename = models.CharField(max_length=255)
    total_rows = models.PositiveIntegerField(default=0)
    unique_combos = models.PositiveIntegerField(default=0)
    duplicates_skipped = models.PositiveIntegerField(default=0)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="csv_imports")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "CSV import"

    def __str__(self) -> str:
        return self.original_filename
