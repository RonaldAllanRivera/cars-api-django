from rest_framework.generics import ListAPIView

from api.v1.filters import ErrorFilter
from api.v1.serializers import ErrorEventSerializer
from apps.accounts import abilities
from apps.observability.models import ErrorEvent


class ErrorListView(ListAPIView):
    """The pipeline error log, newest first."""

    queryset = ErrorEvent.objects.all()
    serializer_class = ErrorEventSerializer
    filterset_class = ErrorFilter
    # occurred_at alone is not unique; id breaks ties so the cursor never skips.
    cursor_ordering = ("-occurred_at", "-id")
    required_ability = abilities.ERRORS_READ
    throttle_scope = "read"
