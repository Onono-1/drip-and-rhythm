import os
import secrets

import dj_database_url
from cryptography.fernet import Fernet

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48)
TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY") or Fernet.generate_key().decode("ascii")

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
if TEST_DATABASE_URL:
    DATABASES["default"] = dj_database_url.parse(TEST_DATABASE_URL, conn_max_age=0)  # noqa: F405
    DATABASES["default"]["TEST"] = {"NAME": DATABASES["default"]["NAME"]}  # noqa: F405
else:
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_DELIVERY_MODE = "local"
RESEND_WEBHOOK_SECRET = os.getenv("RESEND_WEBHOOK_SECRET") or "whsec_dGVzdF9sb2NhbF9zZWNyZXRfa2V5X2Zvcl9zdm14X3ZlcmlmeQ=="  # noqa: S105
