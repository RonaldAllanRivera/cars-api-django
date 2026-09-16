"""
Django settings for Cars Images API.

One flat set of environment variable names (APP_KEY, DB_HOST, WIKIMEDIA_*,
CARS_*, ...) is shared by local, CI and deployed runs, so one .env works
everywhere.
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
    "apps.publishing",
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
        "DIRS": [BASE_DIR / "templates"],  # admin/index.html override
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

# Database-backed cache: needs `manage.py createcachetable`.
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
    "DEFAULT_PAGINATION_CLASS": "api.pagination.CursorEnvelopePagination",
    "EXCEPTION_HANDLER": "api.exceptions.field_errors_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": ["api.throttling.SettingsScopedRateThrottle"],
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "api.negotiation.JSONOnlyContentNegotiation",
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "write": "10/min",
        "review": "60/min",
        "logout": "60/min",
        "read": "120/min",
    },
    # ISO-8601 with a numeric offset, as the clients parse: 2026-01-15T09:00:00+00:00
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%:z",
    "UNAUTHENTICATED_USER": None,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO").upper()},
    # httpx logs every Wikimedia request at INFO.
    "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"}},
}

# ---------------------------------------------------------------------------
# Wikimedia Commons
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
# Pipeline limits
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

# ---------------------------------------------------------------------------
# OpenAI post generation
# ---------------------------------------------------------------------------
# Rates are USD per 1M tokens and are snapshotted onto every AiUsage row, so a
# price change never rewrites what past runs are recorded as having cost.
# Changing OPENAI_MODEL without changing the three rates silently redefines the
# budget cap.
OPENAI = {
    "api_key": env("OPENAI_API_KEY", default=""),
    # Only needed when the key belongs to several organisations; sent as a header when set.
    "organization": env("OPENAI_ORGANIZATION", default=""),
    "base_url": env("OPENAI_BASE_URL", default="https://api.openai.com/v1").rstrip("/"),
    "model": env("OPENAI_MODEL", default="gpt-4o-mini"),
    "timeout": env.float("OPENAI_TIMEOUT", default=90),
    "connect_timeout": env.float("OPENAI_CONNECT_TIMEOUT", default=10),
    "retry_times": env.int("OPENAI_RETRY_TIMES", default=2),
    "retry_sleep_ms": env.int("OPENAI_RETRY_SLEEP_MS", default=500),
    # 700-1200 words of HTML plus four shorter fields, with headroom: a truncated
    # response is discarded, so budgeting too low wastes the whole call.
    "max_completion_tokens": env.int("OPENAI_MAX_COMPLETION_TOKENS", default=3500),
    "temperature": env.float("OPENAI_TEMPERATURE", default=0.7),
    "input_usd_per_1m": env.float("OPENAI_INPUT_USD_PER_1M", default=0.15),
    "cached_input_usd_per_1m": env.float("OPENAI_CACHED_INPUT_USD_PER_1M", default=0.075),
    "output_usd_per_1m": env.float("OPENAI_OUTPUT_USD_PER_1M", default=0.60),
    # 0 disables the cap entirely.
    "monthly_budget_usd": env.float("OPENAI_MONTHLY_BUDGET_USD", default=10.0),
    "reservation_stale_minutes": env.int("OPENAI_RESERVATION_STALE_MINUTES", default=15),
}

# ---------------------------------------------------------------------------
# WordPress publishing
# ---------------------------------------------------------------------------
WORDPRESS = {
    # The site root, without /wp-json: the client appends the route itself.
    "base_url": env("WORDPRESS_BASE_URL", default="").rstrip("/"),
    "username": env("WORDPRESS_USERNAME", default=""),
    # Application Passwords are displayed in groups of four; WordPress strips the
    # spaces before comparing, so a pasted value with them must still work.
    "app_password": env("WORDPRESS_APP_PASSWORD", default="").replace(" ", ""),
    "timeout": env.float("WORDPRESS_TIMEOUT", default=30),
    "upload_timeout": env.float("WORDPRESS_UPLOAD_TIMEOUT", default=60),
    "retry_times": env.int("WORDPRESS_RETRY_TIMES", default=2),
    "retry_sleep_ms": env.int("WORDPRESS_RETRY_SLEEP_MS", default=500),
    # Generated copy is never published unreviewed.
    "post_status": env("WORDPRESS_POST_STATUS", default="draft"),
    # 0 means "send nothing", so an unset value never clears an editor's choice.
    "default_category_id": env.int("WORDPRESS_DEFAULT_CATEGORY_ID", default=0),
    "author_id": env.int("WORDPRESS_AUTHOR_ID", default=0),
    "homepage_url": env("WORDPRESS_HOMEPAGE_URL", default="").rstrip("/"),
    "site_name": env("WORDPRESS_SITE_NAME", default=""),
    # Gutenberg block markup, so a reviewer gets an editable gallery rather than one opaque block.
    "use_blocks": env.bool("WORDPRESS_USE_BLOCKS", default=True),
}

# ---------------------------------------------------------------------------
# Blog publishing limits
# ---------------------------------------------------------------------------
# One post is an OpenAI call plus up to max_images_per_post fetch-resize-upload
# round trips, so the chunk is sized to finish well inside gunicorn's timeout.
CARS_PUBLISHING = {
    "max_posts_per_chunk": env.int("PUBLISH_MAX_POSTS_PER_CHUNK", default=2),
    "chunk_seconds": env.int("PUBLISH_CHUNK_SECONDS", default=60),
    "max_posts_per_day": env.int("PUBLISH_MAX_POSTS_PER_DAY", default=50),
    "sleep_seconds_between_posts": env.float("PUBLISH_SLEEP_SECONDS", default=0.5),
    "max_images_per_post": env.int("PUBLISH_MAX_IMAGES_PER_POST", default=8),
    # Defaults track the export resizer, so posts and ZIPs produce the same picture.
    "image_max_width": env.int("PUBLISH_IMAGE_MAX_WIDTH", default=CARS_IMAGES["download_max_width"]),
    "image_jpeg_quality": env.int("PUBLISH_IMAGE_JPEG_QUALITY", default=CARS_IMAGES["download_jpeg_quality"]),
    "image_fetch_timeout": env.float("PUBLISH_IMAGE_FETCH_TIMEOUT", default=30),
    # Commons originals can be enormous; Pillow decoding one is the memory ceiling on a 512MB instance.
    "image_max_bytes": env.int("PUBLISH_IMAGE_MAX_BYTES", default=25_000_000),
    # A row left mid-run by a killed worker is reclaimed after this long.
    "stale_run_minutes": env.int("PUBLISH_STALE_RUN_MINUTES", default=5),
}
