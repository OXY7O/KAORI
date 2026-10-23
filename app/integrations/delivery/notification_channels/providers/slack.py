from __future__ import annotations

import json
import re
import ssl
from collections.abc import Mapping
from html import escape
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

_SLACK_HOSTS = {'hooks.slack.com', 'hooks.slack-gov.com'}
_SLACK_PATH = re.compile(r'/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9_-]+\Z')
_TEXT_LIMIT = 3000


def _valid_webhook_url(value: str) -> bool:
    """Channel-bound Slack webhook only; never allow arbitrary outbound URLs."""
    if not value or value != value.strip() or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == 'https'
            and parsed.hostname in _SLACK_HOSTS
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.query
            and not parsed.fragment
            and _SLACK_PATH.fullmatch(parsed.path)
        )
    except ValueError:
        return False


def _render_text(message: NotificationMessage) -> str:
    # Slack mrkdwn is enabled by default; HTML-escape special mention/link
    # delimiters instead of passing potentially user-controlled <!here> tokens.
    parts = [f'KAORI · {message.severity.upper()}', message.title, '', message.body]
    if message.action_url:
        parts.extend(['', f'{message.action_label or "Open KAORI"}: {message.action_url}'])
    return escape('\n'.join(parts).strip(), quote=False)[:_TEXT_LIMIT]


def send_slack_message(
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
        return DeliveryResult(False, 'Slack Incoming Webhook URL is missing or not approved.')
    payload = json.dumps({'text': _render_text(message)}, separators=(',', ':')).encode('utf-8')
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
            status = int(getattr(response, 'status', 200) or 200)
            acknowledgement = response.read(64).decode('utf-8', errors='replace').strip()
    except HTTPError as exc:
        if exc.code == 429:
            return DeliveryResult(False, 'Slack webhook rate limited the delivery (HTTP 429).', retry_after_seconds=parse_retry_after(exc.headers.get('Retry-After') if exc.headers else None))
        return DeliveryResult(False, f'Slack webhook rejected delivery with HTTP {exc.code}.')
    except (URLError, TimeoutError, OSError, ValueError):
        return DeliveryResult(False, 'Slack webhook is unreachable or TLS verification failed.')
    if status != 200 or acknowledgement != 'ok':
        return DeliveryResult(False, f'Slack webhook returned an unexpected acknowledgement (HTTP {status}).')
    return DeliveryResult(True, 'Slack webhook accepted the message.')


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    old = credential_map(existing)
    webhook_url = str(form.get('slack_webhook_url') or '').strip()
    return (
        str(form.get('slack_destination') or '').strip(),
        {'webhook_url': webhook_url or old.get('webhook_url', '')},
        {},
        bool(webhook_url),
    )


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors: list[str] = []
    if not data.destination or len(data.destination) > 255:
        errors.append('A Slack destination label is required (up to 255 characters).')
    if not _valid_webhook_url(str(data.credentials.get('webhook_url') or '')):
        errors.append('Enter an approved Slack Incoming Webhook URL.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    return {'slack_destination': channel.destination}
