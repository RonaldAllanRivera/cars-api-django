from decimal import Decimal

from django.db.models import Count, QuerySet
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.responses import data_response
from api.v1.filters import BlogPostFilter
from api.v1.serializers import (
    BlogPostDetailSerializer,
    BlogPostSerializer,
    BlogPostSyncSerializer,
    PublishChunkSerializer,
)
from api.v1.views.base import ActionPolicyMixin
from apps.accounts import abilities
from apps.publishing.models import BlogPost
from apps.publishing.services import seeding
from apps.publishing.services.budget import month_to_date
from apps.publishing.services.run_chunk import run_chunk


class BlogPostViewSet(ActionPolicyMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """AI-written WordPress drafts. Only run-chunk spends AI budget, behind its own ability and throttle."""

    queryset = BlogPost.objects.annotate(images_count=Count("media"))
    serializer_class = BlogPostSerializer
    filterset_class = BlogPostFilter
    lookup_value_converter = "int"
    required_ability = {
        "list": abilities.BLOG_READ,
        "retrieve": abilities.BLOG_READ,
        "budget": abilities.BLOG_READ,
        "sync": abilities.BLOG_WRITE,
        "run_chunk": abilities.BLOG_PUBLISH,
    }
    throttle_scopes = {
        "list": "read",
        "retrieve": "read",
        "budget": "read",
        "sync": "write",
        "run_chunk": "publish",
    }

    def filter_queryset(self, queryset: QuerySet) -> QuerySet:
        return queryset if self.detail else super().filter_queryset(queryset)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        post = self.get_object()
        return data_response(BlogPostDetailSerializer(post).data)

    @action(detail=False, methods=["get"])
    def budget(self, request: Request) -> Response:
        """This month's AI spend against the cap; money as strings so no client rounds it through a float."""
        summary = month_to_date()
        return data_response(
            {
                key: (value.isoformat() if key == "month" else str(value) if isinstance(value, Decimal) else value)
                for key, value in summary.items()
            }
        )

    @action(detail=False, methods=["post"])
    def sync(self, request: Request) -> Response:
        """Queue a post per vehicle with approved images. Spends nothing."""
        serializer = BlogPostSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = seeding.sync_posts(
            csv_import=serializer.validated_data.get("csv_import_id"), requested_by=request.user
        )
        return data_response({"created": result.created, "existing": result.existing})

    @action(detail=False, methods=["post"], url_path="run-chunk")
    def run_chunk(self, request: Request) -> Response:
        """
        Write and publish one bounded slice of posts. A block (budget, rate limit,
        credentials) is a successful response with `blocked` set: it is how the
        client's loop knows to stop, as with /searches/run-chunk.
        """
        serializer = PublishChunkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        csv_import = serializer.validated_data.get("csv_import_id")
        result = run_chunk(
            csv_import_id=csv_import.pk if csv_import else None,
            post_ids=serializer.validated_data.get("post_ids"),
        )
        return Response(result.as_dict())
