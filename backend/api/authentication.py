import hmac

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import ApiToken


class BearerTokenAuthentication(BaseAuthentication):
    """
    Accepts `Authorization: Bearer <id>|<secret>`.

    DRF's TokenAuthentication expects the `Token` keyword and stores tokens in
    plain text; the mobile client sends `Bearer`, and tokens here are hashed.
    """

    keyword = b"bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Unauthenticated.")

        token_id, separator, secret = parts[1].decode(errors="ignore").partition("|")
        if not separator or not token_id.isdigit() or not secret:
            raise AuthenticationFailed("Unauthenticated.")

        token = ApiToken.objects.select_related("user").filter(pk=int(token_id)).first()
        if (
            token is None
            or not hmac.compare_digest(token.token_hash, ApiToken.hash(secret))
            or token.is_expired
            or not token.user.is_active
        ):
            raise AuthenticationFailed("Unauthenticated.")

        ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        return token.user, token

    def authenticate_header(self, request):
        return "Bearer"
