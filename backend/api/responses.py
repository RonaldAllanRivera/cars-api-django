from rest_framework import status as http_status
from rest_framework.response import Response


def data_response(payload, status: int = http_status.HTTP_200_OK, headers=None, **extra) -> Response:
    """Single-resource envelope: {"data": ..., **extra}."""
    return Response({"data": payload, **extra}, status=status, headers=headers)
