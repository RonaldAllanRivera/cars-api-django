from rest_framework.permissions import BasePermission

from apps.accounts.models import ApiToken


def required_ability(request, view) -> str | None:
    """
    Views declare `required_ability` as a string, or as a dict keyed by
    ViewSet action (e.g. {"list": "search:read", "create": "search:write"}).
    """
    declared = getattr(view, "required_ability", None)
    if isinstance(declared, dict):
        return declared.get(getattr(view, "action", None)) or declared.get(request.method)
    return declared


class HasAbility(BasePermission):
    """403 when the bearer token lacks the ability the view declares."""

    message = "Invalid ability provided."

    def has_permission(self, request, view) -> bool:
        ability = required_ability(request, view)
        if ability is None:
            return True
        token = request.auth
        return isinstance(token, ApiToken) and token.can(ability)
