from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import ScopedRateThrottle


class SettingsScopedRateThrottle(ScopedRateThrottle):
    """
    ScopedRateThrottle that reads rates on every request.

    DRF copies DEFAULT_THROTTLE_RATES once at import, so settings overrides
    (tests, per-environment tuning) would otherwise be silently ignored.
    """

    def get_rate(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        try:
            return rates[self.scope]
        except KeyError as exc:
            raise ImproperlyConfigured(f"No throttle rate set for scope {self.scope!r}") from exc
