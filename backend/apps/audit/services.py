from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .logging_filters import redact_text
from .models import AuditLog

SENSITIVE_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "claim_token",
    "admission_token",
    "share_token",
    "receipt_token",
    "secret",
    "cookie",
    "authorization",
    "api_key",
    "qr_payload",
    "encrypted",
}


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(secret_word in key_lower for secret_word in SENSITIVE_KEYS):
                cleaned[str(k)] = "[REDACTED]"
            else:
                cleaned[str(k)] = sanitize_metadata(v)
        return cleaned
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def extract_client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    remote_addr = request.META.get("REMOTE_ADDR", "").strip()
    return remote_addr or None


def log_audit_event(
    *,
    actor: Any = None,
    action_type: str,
    target_type: str,
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    resolved_actor = actor if getattr(actor, "is_authenticated", False) else None
    actor_email = getattr(resolved_actor, "email", "") if resolved_actor else ""
    return AuditLog.objects.create(
        actor=resolved_actor,
        actor_email=actor_email,
        action_type=action_type,
        target_type=target_type,
        target_id=str(target_id) if target_id else "",
        metadata=sanitize_metadata(metadata or {}),
        ip_address=extract_client_ip(request),
    )
