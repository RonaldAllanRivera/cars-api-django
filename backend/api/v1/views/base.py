from django.db.models import QuerySet
from django_filters import FilterSet
from django_filters.utils import translate_validation
from rest_framework.request import Request


class ActionPolicyMixin:
    """
    For ViewSets whose actions are throttled differently: `throttle_scopes`
    maps action names to ScopedRateThrottle scopes, alongside the
    `required_ability` dict that HasAbility reads.
    """

    throttle_scopes: dict[str, str] = {}

    @property
    def throttle_scope(self) -> str | None:
        return self.throttle_scopes.get(getattr(self, "action", None))


def filter_or_422[F: FilterSet](filterset_class: type[F], request: Request, queryset: QuerySet) -> F:
    """A bound, valid FilterSet over the query string, or a 422 in the shared error shape."""
    filterset = filterset_class(request.query_params, queryset=queryset, request=request)
    if not filterset.is_valid():
        raise translate_validation(filterset.errors)
    return filterset
