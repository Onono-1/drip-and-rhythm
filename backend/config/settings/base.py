from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.events",
    "apps.invitations",
    "apps.communications",
    "apps.checkins",
    "apps.audit",
]

MIDDLEWARE = [
    "apps.accounts.middleware.ProxySharedSecretMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ActiveAdminAndCacheControlMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
        )
    }
    DATABASES["default"].setdefault("TEST", {})["NAME"] = "drip_and_rhythm_test"
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "drip_and_rhythm",
            "USER": "drip_app",
            "PASSWORD": "",
            "HOST": "127.0.0.1",
            "PORT": "5432",
            "TEST": {"NAME": "drip_and_rhythm_test"},
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Africa/Kampala")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session & CSRF cookie security
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "drip_admin_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12
CSRF_COOKIE_NAME = "drip_csrf"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# Cryptographic credentials & claim receipt configuration
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")
CLAIM_RECEIPT_COOKIE_NAME = "drip_claim_receipt"
_raw_ttl = os.getenv("CLAIM_RECEIPT_TTL_DAYS", "").strip()
CLAIM_RECEIPT_TTL_DAYS: int | None = int(_raw_ttl) if _raw_ttl.isdigit() and int(_raw_ttl) > 0 else None

# Email & Resend configuration
EMAIL_DELIVERY_MODE = os.getenv("EMAIL_DELIVERY_MODE", "local").strip().lower()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "invitations@dripandrhythm.local").strip()
RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", "DRIP & RHYTHM").strip()
RESEND_REPLY_TO_EMAIL = os.getenv("RESEND_REPLY_TO_EMAIL", "").strip()
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET", "").strip()
EMAIL_MAX_RETRIES = int(os.getenv("EMAIL_MAX_RETRIES", "5"))
EMAIL_WORKER_POLL_INTERVAL = float(os.getenv("EMAIL_WORKER_POLL_INTERVAL", "3"))
EMAIL_WORKER_LEASE_SECONDS = int(os.getenv("EMAIL_WORKER_LEASE_SECONDS", "120"))
EMAIL_INLINE_DISPATCH = env_bool("EMAIL_INLINE_DISPATCH", False)
PROXY_SHARED_SECRET = os.getenv("PROXY_SHARED_SECRET", "").strip()
LOCAL_DEV_OUTPUT_DIR = BASE_DIR / "var" / "dev_emails"

# Assets & fonts
# Render services use rootDir=backend, so a backend-local copy of the authentic poster is preferred;
# the repository-level original remains the canonical source and local fallback.
_POSTER_CANDIDATES = [
    Path(p) for p in [os.getenv("POSTER_IMAGE_PATH", "").strip()] if p
] + [BASE_DIR / "assets" / "event-poster.jpeg", REPO_ROOT / "assets" / "event-poster.jpeg"]
POSTER_IMAGE_PATH = next((p for p in _POSTER_CANDIDATES if p.exists()), _POSTER_CANDIDATES[-1])
FONTS_DIR = BASE_DIR / "static" / "fonts"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.common_pagination.StandardResultsPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.audit.exceptions.custom_exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "URL_FORMAT_OVERRIDE": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "DRIP & RHYTHM Private Party API",
    "DESCRIPTION": "Authoritative API for invitation management, claiming, sharing, and admission.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {
            "()": "apps.audit.logging_filters.SensitiveDataRedactionFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets"],
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
