import secrets

from cryptography.fernet import Fernet

from .base import *  # noqa: F403

DEBUG = env_bool("DJANGO_DEBUG", True)  # noqa: F405

if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = secrets.token_urlsafe(48)

if not TOKEN_ENCRYPTION_KEY:  # noqa: F405
    TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
