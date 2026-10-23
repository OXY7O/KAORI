"""Sanitized provider Retry-After admission for outbound channel transport.

Only the canonical HTTP Retry-After header is used: no provider response body,
error URL, credentials, or untrusted headers are persisted in delivery evidence.
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

MAX_RETRY_AFTER_SECONDS = 86400
_SECONDS = re.compile(r'[0-9]{1,9}(?:\.[0-9]{1,3})?\Z')


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> int | None:
    """Return a bounded nonnegative delay in seconds, or None if malformed.

    Honor RFC 9110 delta-seconds and HTTP-date. Overlong/malformed or past
    dates are rejected; extreme but parseable future delays are capped.
    The scheduler also enforces the existing global minimum delay.
    """
    if not isinstance(value, str) or not value or len(value) > 128 or value != value.strip():
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if _SECONDS.fullmatch(value):
        return min(math.ceil(float(value)), MAX_RETRY_AFTER_SECONDS)
    try:
        deadline = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if deadline is None or deadline.tzinfo is None:
        return None
    current = now if now is not None else datetime.now(UTC)
    remaining = (deadline.astimezone(UTC) - current.astimezone(UTC)).total_seconds()
    if remaining < 0:
        return None
    return min(math.ceil(remaining), MAX_RETRY_AFTER_SECONDS)
