from __future__ import annotations

import json
from typing import Any
from urllib.request import HTTPRedirectHandler, Request

from app.models.notification_channel import NotificationChannel


def credential_map(channel: NotificationChannel | None) -> dict[str, str]:
    if channel is None:
        return {}
    raw = str(channel.credential_payload or '').strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items() if value is not None}


def positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class DenyRedirects(HTTPRedirectHandler):
    """Fail closed for provider HTTP redirects, including to private network targets."""

    def redirect_request(self, request: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None
