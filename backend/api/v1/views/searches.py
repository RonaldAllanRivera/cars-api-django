import logging

from django.db.models import Count, Prefetch, QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.responses import data_response
from api.v1.filters import ImageFilter, SearchFilter
from api.v1.serializers import (
    ImageSerializer,
    RunChunkSerializer,
    SearchCreateSerializer,
    SearchSerializer,
    SearchWithImagesSerializer,
)
from api.v1.views.base import ActionPolicyMixin, filter_or_422
from apps.accounts import abilities
from apps.images.models import CarImage
from apps.searches.models import CarSearch
from apps.searches.services import search_service
from apps.searches.services.run_chunk import run_chunk
from apps.searches.services.run_query import run_search_query
from apps.searches.services.wikimedia import WikimediaBlockedError

logger = logging.getLogger(__name__)


class SearchViewSet(ActionPolicyMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = CarSearch.objects.annotate(images_count=Count("images"))
    serializer_class = SearchSerializer
    filterset_class = SearchFilter
    lookup_value_converter = "int"
    required_ability = {
        "list": abilities.SEARCH_READ,
        "retrieve": abilities.SEARCH_READ,
        "images": abilities.SEARCH_READ,
        "create": abilities.SEARCH_WRITE,
        "run_chunk": abilities.SEARCH_RUN,
    }
    # Both writes reach Wikimedia, which has blocked this app before.
    throttle_scopes = {"list": "read", "retrieve": "read", "images": "read", "create": "write", "run_chunk": "write"}

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        return queryset if self.detail else super().filter_queryset(queryset)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        return data_response(self.get_serializer(self.get_object()).data)

    @action(detail=True)
    def images(self, request: Request, pk: int) -> Response:
        """One search's images, with the same filters as /images."""
        search = self.get_object()
        filterset = filter_or_422(ImageFilter, request, CarImage.objects.filter(car_search=search))
        page = self.paginate_queryset(filterset.qs)
        return self.get_paginated_response(ImageSerializer(page, many=True).data)

    def create(self, request: Request) -> Response:
        """
        Create a search and run it inside this request (there is no worker).
        An identical completed search is handed back instead, sparing Wikimedia.
        """
        serializer = SearchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data

        existing = search_service.find_existing_completed_search(**fields)
        if existing is not None:
            return self._search_response(existing, status.HTTP_200_OK)

        search = search_service.create_search(requested_by=request.user, **fields)
        try:
            run_search_query(search)
        except WikimediaBlockedError as exc:
            retry_after = exc.retry_after_seconds
            return self._search_response(
                search,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                message="Wikimedia is rate-limiting this server. Try again later.",
                retry_after_seconds=retry_after,
                headers={"Retry-After": str(retry_after)} if retry_after else None,
            )
        except Exception:
            # run_search_query has already marked the search failed and logged an error event.
            logger.exception("Inline search %s failed", search.pk)
            return self._search_response(
                search, status.HTTP_502_BAD_GATEWAY, message="The search failed. The reason is in the error log."
            )

        return self._search_response(search, status.HTTP_201_CREATED)

    def _search_response(self, search: CarSearch, code: int, headers: dict | None = None, **extra) -> Response:
        images = Prefetch("images", CarImage.objects.order_by("id"))
        search = self.get_queryset().prefetch_related(images).get(pk=search.pk)
        return Response({**extra, "data": SearchWithImagesSerializer(search).data}, status=code, headers=headers)

    @action(detail=False, methods=["post"], url_path="run-chunk")
    def run_chunk(self, request: Request) -> Response:
        """
        Run one bounded slice of an import's outstanding searches. An empty
        queue is a successful empty response: it is how the client's loop ends.
        """
        serializer = RunChunkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = run_chunk(serializer.validated_data["csv_import_id"].pk)
        return Response(result.as_dict())
