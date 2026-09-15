import csv
import io
import tempfile
from pathlib import Path

from django.conf import settings
from django.db.models import QuerySet
from django.http import FileResponse, HttpRequest, HttpResponse, StreamingHttpResponse
from django.utils import timezone
from django.views import View
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1 import export_links
from api.v1.filters import ImageFilter
from api.v1.serializers import ExportFormatSerializer
from apps.accounts import abilities
from apps.exports.services.csv_exporter import export_rows
from apps.exports.services.zip_builder import build_zip_to_file
from apps.images.models import CarImage


def zip_cap() -> int:
    """A ZIP is built synchronously, one Wikimedia fetch per image, so it is capped."""
    return settings.CARS_IMAGES["bulk_download_max_images"]


class ExportCreateView(APIView):
    """
    Mint a signed link to a CSV or ZIP of the filtered image set. The app opens
    it in the system browser, which owns the long download.
    """

    required_ability = abilities.EXPORTS_READ
    throttle_scope = "write"

    def post(self, request: Request) -> Response:
        format_serializer = ExportFormatSerializer(data=request.data)
        format_valid = format_serializer.is_valid()
        filterset = ImageFilter(request.data, queryset=CarImage.objects.all(), request=request)
        if not format_valid or not filterset.is_valid():
            errors = {**format_serializer.errors, **filterset.errors}
            raise ValidationError({field: [str(message) for message in messages] for field, messages in errors.items()})

        export_format = format_serializer.validated_data["format"]
        count = filterset.qs.count()
        # A link to an empty file is a worse answer than saying so.
        if count == 0:
            raise ValidationError({"format": "No images match these filters."})
        # The cap bounds Wikimedia fetches; a CSV fetches nothing.
        if export_format == "zip" and count > zip_cap():
            raise ValidationError(
                {"format": f"{count} images match; a ZIP is limited to {zip_cap()}. Narrow the filter."}
            )

        url, expires_at = export_links.mint(request, export_format, filterset.validated_params())
        return Response(
            {
                "url": url,
                "expires_at": expires_at.isoformat(),
                "count": count,
                "format": export_format,
            },
            status=status.HTTP_201_CREATED,
        )


class _Echo:
    """A write-through buffer, so csv.writer can feed a streaming response."""

    def write(self, value: str) -> str:
        return value


class _DeleteOnClose(io.FileIO):
    """A read handle that removes its (temporary) file once the response is sent."""

    def close(self) -> None:
        try:
            super().close()
        finally:
            Path(self.name).unlink(missing_ok=True)


class ExportDownloadView(View):
    """
    Serves a signed export link. No bearer token: the signature is the
    credential. Errors are plain text because a browser tab shows them.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        if not export_links.verify(request.GET):
            return _plain("This download link is invalid or has expired.", status.HTTP_403_FORBIDDEN)

        filterset = ImageFilter(export_links.filters_from(request.GET), queryset=CarImage.objects.all())
        if not filterset.is_valid():
            return _plain("This export's filters are no longer valid. Export again from the app.", 422)
        images = filterset.qs.select_related("car_search").order_by("id")
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")

        if request.GET.get("format") == "zip":
            return self._zip(request, images, f"cars-{stamp}.zip")
        return self._csv(images, f"cars-{stamp}.csv")

    def _csv(self, images: QuerySet, filename: str) -> StreamingHttpResponse:
        writer = csv.writer(_Echo(), lineterminator="\n")
        return StreamingHttpResponse(
            (writer.writerow(row) for row in export_rows(images.iterator())),
            content_type="text/csv; charset=UTF-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _zip(self, request: HttpRequest, images: QuerySet, filename: str) -> HttpResponse:
        if not export_links.consume_nonce(request.GET.get("nonce")):
            return _plain("This download link has already been used. Export again from the app.", 410)

        # Recounted rather than trusted from the mint: images can arrive in between.
        if images.count() > zip_cap():
            return _plain(
                "More images match now than a ZIP allows. Export again from the app with a narrower filter.", 422
            )

        matched = list(images)
        with tempfile.NamedTemporaryFile(prefix="cars-export-", suffix=".zip", delete=False) as handle:
            path = handle.name
        try:
            added = build_zip_to_file(matched, path)
        except BaseException:
            Path(path).unlink(missing_ok=True)
            raise
        if added == 0:
            Path(path).unlink(missing_ok=True)
            # An empty archive would look like a successful export of nothing.
            return _plain("None of the images could be fetched from Wikimedia. Try again in a moment.", 502)

        # A side effect on a GET is tolerable only because the nonce makes it fire once per mint.
        CarImage.objects.filter(pk__in=[image.pk for image in matched]).update(
            download_status=CarImage.DownloadStatus.DOWNLOADED, updated_at=timezone.now()
        )
        return FileResponse(_DeleteOnClose(path), as_attachment=True, filename=filename, content_type="application/zip")


def _plain(message: str, code: int) -> HttpResponse:
    return HttpResponse(message, status=code, content_type="text/plain; charset=utf-8")
