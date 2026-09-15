import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _isolated_settings(settings):
    """Fast, deterministic defaults for every test."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Production uses the hashed manifest storage, which needs collectstatic first.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.CARS_IMAGES = {**settings.CARS_IMAGES, "bulk_run_sleep_seconds_between_queries": 0}
    settings.WIKIMEDIA = {**settings.WIKIMEDIA, "retry_sleep_ms": 0}
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {k: "10000/min" for k in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]},
    }
    cache.clear()
    yield
    cache.clear()
