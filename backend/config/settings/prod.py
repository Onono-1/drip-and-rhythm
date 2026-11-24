import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False
EMAIL_INLINE_DISPATCH = env_bool("EMAIL_INLINE_DISPATCH", True)  # noqa: F405

_render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, _render_host]  # noqa: F405

if not SECRET_KEY or len(SECRET_KEY) < 32:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to at least 32 characters in production.")

if not TOKEN_ENCRYPTION_KEY:  # noqa: F405
    raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEY must be configured in production.")

if not DATABASE_URL:  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL must be configured in production.")

if EMAIL_DELIVERY_MODE == "resend" and not RESEND_API_KEY:  # noqa: F405
    raise ImproperlyConfigured("RESEND_API_KEY is required when EMAIL_DELIVERY_MODE=resend.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
