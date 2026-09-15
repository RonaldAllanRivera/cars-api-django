"""
Django settings for Cars Images API.

Environment variable names are shared with the original Laravel project
(APP_KEY, DB_HOST, WIKIMEDIA_*, CARS_*, ...) so one .env works everywhere.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
for candidate in (BASE_DIR / ".env", BASE_DIR.parent / ".env"):
    if candidate.exists():
        environ.Env.read_env(candidate)
        break

APP_ENV = env("APP_ENV", default="local")
APP_NAME = env("APP_NAME", default="Cars Images API")
APP_URL = env("APP_URL", default="http://localhost:8000").rstrip("/")

SECRET_KEY = env("APP_KEY", default="django-insecure-local-development-key-change-me")
DEBUG = env.bool("APP_DEBUG", default=APP_ENV == "local")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"] if DEBUG else [])
_app_host = APP_URL.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
if _app_host and _app_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_app_host)
if render_host := env("RENDER_EXTERNAL_HOSTNAME", default=""):
    ALLOWED_HOSTS.append(render_host)

CSRF_TRUSTED_ORIGINS = [APP_URL] if APP_URL.startswith("https://") else []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "apps.accounts",
    "apps.catalog",
    "apps.imports",
    "apps.searches",
    "apps.images",
    "apps.exports",
    "apps.observability",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — DATABASE_URL wins when set (Render/Neon); otherwise DB_* names.
# ---------------------------------------------------------------------------
if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": env("DB_HOST", default="127.0.0.1"),
            "PORT": env("DB_PORT", default="5434"),
            "NAME": env("DB_DATABASE", default="cars_images_api"),
            "USER": env("DB_USERNAME", default="cars_images_api"),
            "PASSWORD": env("DB_PASSWORD", default="secret"),
        }
    }
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
# Lets parallel test runs use separate databases: DB_TEST_DATABASE=test_x pytest
if db_test_name := env("DB_TEST_DATABASE", default=""):
    DATABASES["default"]["TEST"] = {"NAME": db_test_name}
if db_sslmode := env("DB_SSLMODE", default=""):
    DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = db_sslmode

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Laravel's CACHE_STORE=database equivalent: needs `manage.py createcachetable`.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache"
        if env("CACHE_STORE", default="database") == "database"
        else "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "cache",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# Security (production)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# CORS — API only, origins from CORS_ALLOWED_ORIGINS (comma-separated)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in env.list("CORS_ALLOWED_ORIGINS", default=[]) if o.strip()]
CORS_URLS_REGEX = r"^/api/.*$"
CORS_PREFLIGHT_MAX_AGE = 3600

# The mobile client calls paths without trailing slashes.
APPEND_SLASH = False

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["api.authentication.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "api.permissions.HasAbility",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.LaravelCursorPagination",
    "EXCEPTION_HANDLER": "api.exceptions.laravel_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["api.throttling.SettingsScopedRateThrottle"],
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "api.negotiation.JSONOnlyContentNegotiation",
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "write": "10/min",
        "review": "60/min",
        "logout": "60/min",
        "read": "120/min",
    },
    # Matches Laravel's ISO-8601 output: 2026-01-15T09:00:00+00:00
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%:z",
    "UNAUTHENTICATED_USER": None,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO").upper()},
}

# ---------------------------------------------------------------------------
# Wikimedia Commons (Laravel config/images.php)
# ---------------------------------------------------------------------------
WIKIMEDIA = {
    "base_url": env("WIKIMEDIA_BASE_URL", default="https://commons.wikimedia.org/w/api.php"),
    "user_agent": env(
        "WIKIMEDIA_USER_AGENT",
        default="CarsImagesApi/1.0 (https://github.com/RonaldAllanRivera/cars-api-django)",
    ),
    "timeout": env.float("WIKIMEDIA_TIMEOUT", default=10),
    "retry_times": env.int("WIKIMEDIA_RETRY_TIMES", default=3),
    "retry_sleep_ms": env.int("WIKIMEDIA_RETRY_SLEEP_MS", default=200),
    "cache_ttl": env.int("WIKIMEDIA_CACHE_TTL", default=3600),
    "maxlag": env.int("WIKIMEDIA_MAXLAG", default=5),
    "category_miss_ttl_days": env.int("WIKIMEDIA_CATEGORY_MISS_TTL_DAYS", default=30),
    "category_max_files": env.int("WIKIMEDIA_CATEGORY_MAX_FILES", default=500),
    "category_page_size": env.int("WIKIMEDIA_CATEGORY_PAGE_SIZE", default=200),
}

# ---------------------------------------------------------------------------
# Pipeline limits (Laravel config/cars-images.php)
# ---------------------------------------------------------------------------
CARS_IMAGES = {
    "csv_import_max_combos": env.int("CSV_IMPORT_MAX_COMBOS", default=1000),
    "csv_import_default_images_per_year": env.int("CSV_IMPORT_DEFAULT_IMAGES_PER_YEAR", default=5),
    "csv_import_max_upload_kb": env.int("CSV_IMPORT_MAX_UPLOAD_KB", default=5120),
    "csv_import_max_projected_images": env.int("CSV_IMPORT_MAX_PROJECTED_IMAGES", default=5000),
    "error_log_retention_days": env.int("ERROR_LOG_RETENTION_DAYS", default=30),
    "error_log_max_events_per_import": env.int("ERROR_LOG_MAX_EVENTS_PER_IMPORT", default=500),
    "bulk_run_max_queries_per_chunk": env.int("CARS_BULK_RUN_MAX_QUERIES", default=50),
    "bulk_run_max_seconds_per_chunk": env.int("CARS_BULK_RUN_MAX_SECONDS", default=50),
    "bulk_run_auto_chunk_seconds": env.int("CARS_BULK_RUN_AUTO_CHUNK_SECONDS", default=10),
    "bulk_run_sleep_seconds_between_queries": env.float("CARS_BULK_RUN_SLEEP_SECONDS", default=1),
    "download_max_width": env.int("CARS_DOWNLOAD_MAX_WIDTH", default=1600),
    "download_jpeg_quality": env.int("CARS_DOWNLOAD_JPEG_QUALITY", default=82),
    "bulk_download_max_images": env.int("CARS_BULK_DOWNLOAD_MAX_IMAGES", default=100),
    "api_search_max_year_span": env.int("API_SEARCH_MAX_YEAR_SPAN", default=3),
    "api_search_max_images_per_year": env.int("API_SEARCH_MAX_IMAGES_PER_YEAR", default=5),
    "export_link_ttl_seconds": env.int("EXPORT_LINK_TTL_SECONDS", default=300),
}
