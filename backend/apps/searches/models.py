from django.conf import settings
from django.db import models
from django.utils import timezone


class CarSearch(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    make = models.CharField(max_length=255)
    model = models.CharField(max_length=255, null=True, blank=True)
    commons_category = models.CharField(max_length=255, null=True, blank=True)
    from_year = models.PositiveSmallIntegerField()
    to_year = models.PositiveSmallIntegerField()
    color = models.CharField(max_length=64, null=True, blank=True)
    transmission = models.CharField(max_length=255, null=True, blank=True)
    transparent_background = models.BooleanField(default=False)
    images_per_year = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="car_searches")
    # Deleting an import removes its queued searches (and, via CarImage, their images).
    csv_import = models.ForeignKey(
        "imports.CsvImport", on_delete=models.CASCADE, null=True, blank=True, related_name="searches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "car search"
        verbose_name_plural = "car searches"

    def __str__(self) -> str:
        years = str(self.from_year) if self.from_year == self.to_year else f"{self.from_year}-{self.to_year}"
        return " ".join(part for part in (years, self.make, self.model) if part)


class CommonsCategoryLookup(models.Model):
    """Resolved Commons category per make/model. category=NULL records a known miss."""

    make = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    category = models.CharField(max_length=255, null=True, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["make", "model"], name="commons_category_lookups_make_model_unique")
        ]

    def __str__(self) -> str:
        return f"{self.make} {self.model} → {self.category or '∅'}"


class WikimediaBlockEvent(models.Model):
    car_search = models.ForeignKey(
        CarSearch, on_delete=models.SET_NULL, null=True, blank=True, related_name="block_events"
    )
    csv_import = models.ForeignKey(
        "imports.CsvImport", on_delete=models.SET_NULL, null=True, blank=True, related_name="block_events"
    )
    status_code = models.PositiveSmallIntegerField()
    retry_after_seconds = models.PositiveIntegerField(null=True, blank=True)
    response_excerpt = models.TextField(null=True, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"HTTP {self.status_code} at {self.occurred_at:%Y-%m-%d %H:%M}"
