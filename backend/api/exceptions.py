from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _flatten(detail, prefix: str = "") -> dict[str, list[str]]:
    """Flatten DRF's nested error detail into the {"field": ["msg"]} shape clients expect."""
    if isinstance(detail, dict):
        errors: dict[str, list[str]] = {}
        for key, value in detail.items():
            name = "message" if key in ("non_field_errors", "__all__") and not prefix else key
            errors.update(_flatten(value, f"{prefix}.{name}" if prefix else str(name)))
        return errors
    if isinstance(detail, list):
        if all(not isinstance(item, (dict, list)) for item in detail):
            return {prefix or "message": [str(item) for item in detail]}
        errors = {}
        for index, item in enumerate(detail):
            errors.update(_flatten(item, f"{prefix}.{index}" if prefix else str(index)))
        return errors
    return {prefix or "message": [str(detail)]}


def validation_message(errors: dict[str, list[str]]) -> str:
    messages = [message for field in errors.values() for message in field]
    if not messages:
        return "The given data was invalid."
    extra = len(messages) - 1
    if extra == 0:
        return messages[0]
    return f"{messages[0]} (and {extra} more error{'s' if extra > 1 else ''})"


def validation_response(errors: dict[str, list[str]]) -> Response:
    return Response(
        {"message": validation_message(errors), "errors": errors},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def field_errors_exception_handler(exc, context):
    """
    Error bodies the clients understand:
      422 {"message", "errors"} for validation, {"message"} for everything else.
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.ValidationError):
        return validation_response(_flatten(exc.detail))

    response = exception_handler(exc, context)
    if response is None:
        return None

    messages = {
        exceptions.NotAuthenticated: "Unauthenticated.",
        exceptions.AuthenticationFailed: "Unauthenticated.",
        exceptions.NotFound: "Not found.",
        exceptions.Throttled: "Too Many Attempts.",
    }
    message = next((text for kind, text in messages.items() if isinstance(exc, kind)), None)
    if message is None:
        detail = getattr(exc, "detail", None)
        message = str(detail) if detail is not None else "Server Error"

    response.data = {"message": message}
    return response
