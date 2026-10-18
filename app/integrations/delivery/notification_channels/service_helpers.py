from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.models.notification_channel import NotificationChannel


@dataclass(frozen=True, slots=True)
class DeliveryPagination:
    page: int = 1
    per_page: int = 5


def _reset_channel_validation(channel: NotificationChannel) -> None:
    channel.test_status = 'not_tested'
    channel.test_message = 'Destination, credentials, or transport configuration changed. Validate the channel again.'
    channel.last_tested_at = None
    channel.last_delivery_status = 'never'
    channel.last_delivery_message = None
    channel.last_delivery_attempt_at = None
    channel.last_delivery_at = None


def _encode_credentials(credentials: dict[str, str]) -> str:
    return json.dumps(credentials, separators=(',', ':'), sort_keys=True)


def _credential_map(channel: NotificationChannel) -> dict[str, str]:
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


def _normalize_severity(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'critical', 'error', 'fatal', 'p1'}:
        return 'critical'
    if normalized in {'warning', 'warn', 'p2'}:
        return 'warning'
    return 'info'


def _minimum_severity_label(value: str) -> str:
    return {
        'critical': 'Critical only',
        'warning': 'Warning and Critical',
        'info': 'Info and above',
    }.get(value, 'Warning and Critical')
