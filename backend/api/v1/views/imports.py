from django.db.models import Count
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.responses import data_response
from api.v1.serializers import ImportDetailSerializer, ImportSerializer, ImportUploadSerializer
from api.v1.views.base import ActionPolicyMixin
from apps.accounts import abilities
from apps.imports.models import CsvImport
from apps.imports.services.coverage import import_coverage
from apps.imports.services.csv_importer import CsvImportError, import_csv


class ImportViewSet(ActionPolicyMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    CSV imports. The list omits coverage (six aggregates per row is a fan-out
    on a screen that only identifies the import); the detail carries it.
    """

    queryset = CsvImport.objects.select_related("imported_by").annotate(searches_count=Count("searches"))
    serializer_class = ImportSerializer
    lookup_value_converter = "int"
    required_ability = {
        "list": abilities.IMPORTS_READ,
        "retrieve": abilities.IMPORTS_READ,
        "create": abilities.IMPORTS_WRITE,
    }
    # Upload seeds up to csv_import_max_combos future Wikimedia calls.
    throttle_scopes = {"list": "read", "retrieve": "read", "create": "write"}

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        return self._detail_response(self.get_object())

    def create(self, request: Request) -> Response:
        serializer = ImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = import_csv(serializer.validated_data["csv_file"], request.user)
        except CsvImportError as exc:
            # Already logged under csv_upload; as a 422 on the field, the message
            # lands under the file picker rather than in a generic banner.
            raise ValidationError({"csv_file": str(exc)}) from exc

        return self._detail_response(self.get_queryset().get(pk=result.csv_import.pk), status.HTTP_201_CREATED)

    def _detail_response(self, csv_import: CsvImport, code: int = status.HTTP_200_OK) -> Response:
        context = {**self.get_serializer_context(), "coverage": import_coverage(csv_import.pk)}
        return data_response(ImportDetailSerializer(csv_import, context=context).data, status=code)
