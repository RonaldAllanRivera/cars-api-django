from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.responses import data_response
from api.v1.filters import ImageFilter
from api.v1.serializers import ImageSerializer, ReviewSerializer
from api.v1.views.base import ActionPolicyMixin
from apps.accounts import abilities
from apps.images.models import CarImage


class ImageViewSet(ActionPolicyMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The image grid: newest first, cursor-paginated, filterable."""

    queryset = CarImage.objects.all()
    serializer_class = ImageSerializer
    filterset_class = ImageFilter
    lookup_value_converter = "int"
    required_ability = {
        "list": abilities.SEARCH_READ,
        "count": abilities.SEARCH_READ,
        "retrieve": abilities.SEARCH_READ,
        "review": abilities.REVIEW_WRITE,
    }
    throttle_scopes = {"list": "read", "count": "read", "retrieve": "read", "review": "review"}

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        # Filters narrow collections; a lookup by id ignores them.
        return queryset if self.detail else super().filter_queryset(queryset)

    @action(detail=False)
    def count(self, request: Request) -> Response:
        """
        How many images match the list's filters. The list is cursor-paginated
        and carries no total, so this answers the one question it cannot.
        """
        return Response({"count": self.filter_queryset(self.get_queryset()).count()})

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        return data_response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["patch"])
    def review(self, request: Request, pk: int) -> Response:
        """
        Record the human verdict. Only the review columns change; the machine's
        make/year verdicts are left alone. "Pending" carries no reviewer.
        """
        image = self.get_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image.review_status = serializer.validated_data["review_status"]
        if image.review_status == CarImage.ReviewStatus.PENDING:
            image.reviewed_by, image.reviewed_at = None, None
        else:
            image.reviewed_by, image.reviewed_at = request.user, timezone.now()
        image.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "updated_at"])

        return data_response(ImageSerializer(image).data)
