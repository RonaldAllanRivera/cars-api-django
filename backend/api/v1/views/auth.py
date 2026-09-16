from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.responses import data_response
from api.v1.serializers import LoginSerializer, UserSerializer
from apps.accounts import abilities
from apps.accounts.models import ApiToken


class LoginView(APIView):
    """Exchange credentials for a bearer token carrying the requested scope, or the default one."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credentials = serializer.validated_data

        user = authenticate(request, email=credentials["email"], password=credentials["password"])
        if user is None:
            # One message for "no such account" and "wrong password", so the
            # endpoint cannot be used to discover which emails exist.
            raise ValidationError({"email": "These credentials do not match our records."})

        granted = abilities.resolve(credentials.get("abilities"), staff=user.is_staff)
        _, plain = ApiToken.issue(user, credentials["device_name"], granted)

        return Response(
            {"token": plain, "token_type": "Bearer", "abilities": granted, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """Revoke the token that made this request, and only that one."""

    throttle_scope = "logout"

    def post(self, request: Request) -> Response:
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """The app's "is my token still good?" probe."""

    throttle_scope = "read"

    def get(self, request: Request) -> Response:
        return data_response(UserSerializer(request.user).data)
