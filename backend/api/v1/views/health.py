from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.responses import data_response
from apps.accounts import abilities
from apps.observability.services.health import pipeline_health_summary


class HealthSummaryView(APIView):
    required_ability = abilities.ERRORS_READ
    throttle_scope = "read"

    def get(self, request: Request) -> Response:
        summary = pipeline_health_summary()
        summary["latest_error_at"] = serializers.DateTimeField().to_representation(summary["latest_error_at"])
        return data_response(summary)
