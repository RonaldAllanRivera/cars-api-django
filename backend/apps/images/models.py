from django.conf import settings
from django.db import models


class CarImage(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class DownloadStatus(models.TextChoices):
        NOT_DOWNLOADED = "not_downloaded", "Not downloaded"
        DOWNLOADING = "downloading", "Downloading"
        DOWNLOADED = "downloaded", "Downloaded"
        FAILED = "failed", "Failed"

    car_search = models.ForeignKey(
        "searches.CarSearch", on_delete=models.CASCADE, null=True, blank=True, related_name="images"
    )
    make = models.CharField(max_length=255, db_index=True)
    model = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    color = models.CharField(max_length=64, null=True, blank=True)
    transparent_background = models.BooleanField(default=False)
    provider = models.CharField(max_length=32, default="wikimedia")
    provider_image_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    title = models.TextField()
    description = models.TextField(null=True, blank=True)
    source_url = models.TextField()
    thumbnail_url = models.TextField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    license = models.CharField(max_length=255, null=True, blank=True)
    attribution = models.TextField(null=True, blank=True)
    # NULL = not evaluated.
    make_confirmed = models.BooleanField(null=True, blank=True)
    year_confirmed = models.BooleanField(null=True, blank=True)
    review_status = models.CharField(
        max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_images"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    download_status = models.CharField(
        max_length=32, choices=DownloadStatus.choices, default=DownloadStatus.NOT_DOWNLOADED, db_index=True
    )
    download_path = models.CharField(max_length=512, null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["make", "model", "year"], name="car_images_make_model_year_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["car_search", "year", "provider", "provider_image_id"],
                name="car_images_owner_provider_unique",
            )
        ]

    def __str__(self) -> str:
        return self.title
