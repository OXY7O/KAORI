from __future__ import annotations

import json
import re
import ssl
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.form_support import (
    DenyRedirects,
    credential_map,
)
from app.models.notification_channel import NotificationChannel
from app.integrations.delivery.notification_channels.retry_after import parse_retry_after

_WEBHOOK_PATH = re.compile(r'/api/(?:v[0-9]+/)?webhooks/[0-9]{10,22}/[A-Za-z0-9._-]+\Z')
_DISCORD_LIMIT = 2000


def _valid_webhook_url(value: str) -> bool:
    """Pin to an official channel-bound Discord webhook, never a generic URL."""
    if not value or value != value.strip() or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == 'https'
            and parsed.hostname == 'discord.com'
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.query
            and not parsed.fragment
            and _WEBHOOK_PATH.fullmatch(parsed.path)
        )
    except ValueError:
        return False


def _render_content(message: NotificationMessage) -> str:
    parts = [f'KAORI · {message.severity.upper()}', message.title, '', message.body]
    if message.action_url:
        parts.extend(['', f'{message.action_label or "Open KAORI"}: {message.action_url}'])
    return '\n'.join(parts).strip()[:_DISCORD_LIMIT]


def send_discord_message(
    *,
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int = 10,
) -> DeliveryResult:
    del destination, provider_config
    webhook_url = str(credentials.get('webhook_url') or '')
    if not _valid_webhook_url(webhook_url):
        return DeliveryResult(False, 'Discord Webhook URL is missing or not approved.')
    payload = json.dumps(
        {'content': _render_content(message), 'allowed_mentions': {'parse': []}},
        separators=(',', ':'),
    ).encode('utf-8')
    request = Request(
        webhook_url,
        data=payload,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    try:
        with build_opener(
            ProxyHandler({}),
            HTTPSHandler(context=ssl.create_default_context()),
            DenyRedirects(),
        ).open(request, timeout=max(int(timeout_seconds), 1)) as response:
            status = int(getattr(response, 'status', 204) or 204)
            raw = response.read(8192) if status == 200 else b''
    except HTTPError as exc:
        if exc.code == 429:
            delay = parse_retry_after(exc.headers.get('Retry-After') if exc.headers else None)
            return DeliveryResult(
                False,
                'Discord webhook rate limited the delivery (HTTP 429).',
                retry_after_seconds=delay,
            )
        return DeliveryResult(False, f'Discord webhook rejected delivery with HTTP {exc.code}.')
    except (URLError, TimeoutError, OSError, ValueError):
        return DeliveryResult(False, 'Discord webhook is unreachable or TLS verification failed.')
    if status not in (200, 204):
        return DeliveryResult(False, f'Discord webhook returned HTTP {status}.')
    provider_id = None
    if status == 200:
        try:
            ack = json.loads(raw)
            if not isinstance(ack, dict):
                raise ValueError('Invalid acknowledgement')
            message_id = ack.get('id')
            provider_id = str(message_id)[:120] if message_id is not None else None
        except (ValueError, TypeError):
            return DeliveryResult(False, 'Discord returned an invalid webhook acknowledgement.')
    return DeliveryResult(True, 'Discord webhook accepted the message.', provider_id)


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    old = credential_map(existing)
    webhook_url = str(form.get('discord_webhook_url') or '').strip()
    return (
        str(form.get('discord_destination') or '').strip(),
        {'webhook_url': webhook_url or old.get('webhook_url', '')},
        {},
        bool(webhook_url),
    )


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors = []
    if not data.destination or len(data.destination) > 255:
        errors.append('A Discord destination label is required (up to 255 characters).')
    if not _valid_webhook_url(str(data.credentials.get('webhook_url') or '')):
        errors.append('Enter an approved Discord channel webhook URL.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    return {'discord_destination': channel.destination}
