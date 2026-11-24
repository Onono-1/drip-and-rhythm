from __future__ import annotations

import logging
import re

TOKEN_PATTERNS = [
    (re.compile(r"(/invite/)[A-Za-z0-9_-]{12,}"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(/share/)[A-Za-z0-9_-]{12,}"), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(DRIP1:)[A-Za-z0-9_-]+"), r"\1[REDACTED_QR]"),
    (re.compile(r"(whsec_)[A-Za-z0-9_+/=-]+"), r"\1[REDACTED_SECRET]"),
    (re.compile(r"(re_)[A-Za-z0-9_-]{10,}"), r"\1[REDACTED_KEY]"),
    (re.compile(r"(drip_claim_receipt=)[^;\s]+"), r"\1[REDACTED_COOKIE]"),
    (re.compile(r"(drip_admin_session=)[^;\s]+"), r"\1[REDACTED_COOKIE]"),
]


def redact_text(value: str) -> str:
    result = value
    for pattern, repl in TOKEN_PATTERNS:
        result = pattern.sub(repl, result)
    return result


class SensitiveDataRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(arg) if isinstance(arg, str) else arg for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: redact_text(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
        return True
