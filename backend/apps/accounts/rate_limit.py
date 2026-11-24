from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from django.db import connection
from django.http import HttpRequest
from rest_framework import status

from apps.audit.exceptions import ApplicationError


def _hash_identifier(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:48]


def enforce_rate_limit(
    request: HttpRequest | None,
    *,
    scope: str,
    key: str | None = None,
    limit: int,
    window_seconds: int,
) -> None:
    if key:
        raw_id = key
    elif request is not None:
        proxy_ip = (
            request.META.get("HTTP_X_DRIP_CLIENT_IP", "").strip()
            if getattr(request, "proxy_verified", False)
            else ""
        )
        raw_id = proxy_ip or request.META.get("REMOTE_ADDR", "unknown") or "unknown"
    else:
        raw_id = "global"

    identifier = _hash_identifier(raw_id)
    now_ts = int(datetime.now(tz=UTC).timestamp())
    bucket_epoch = now_ts - (now_ts % window_seconds)
    window_start = datetime.fromtimestamp(bucket_epoch, tz=UTC)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO accounts_ratelimitbucket (scope, identifier, window_start, hit_count)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (scope, identifier, window_start)
            DO UPDATE SET hit_count = accounts_ratelimitbucket.hit_count + 1
            RETURNING hit_count
            """,
            [scope, identifier, window_start],
        )
        row = cursor.fetchone()
        current_hits = int(row[0]) if row else 1

    if current_hits > limit:
        raise ApplicationError(
            code="RATE_LIMITED",
            message="Too many requests. Please wait a moment and try again.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
