from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def generate_secure_token() -> str:
    """Generate a 256-bit cryptographically random URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def _get_fernet() -> Fernet:
    raw_key = (settings.TOKEN_ENCRYPTION_KEY or "").strip()
    if not raw_key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not configured.")
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("ascii"))
        if len(decoded) == 32:
            return Fernet(raw_key.encode("ascii"))
    except Exception:
        pass
    derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
    return Fernet(derived)


def encrypt_token(raw_token: str) -> str:
    if not raw_token:
        return ""
    return _get_fernet().encrypt(raw_token.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored credential.") from exc
