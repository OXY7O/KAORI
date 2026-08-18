from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.form_support import credential_map
from app.models.notification_channel import NotificationChannel

_TELEGRAM_API = 'https://api.telegram.org'
_TELEGRAM_TEXT_LIMIT = 4096


def send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    message: NotificationMessage,
    timeout_seconds: int = 10,
) -> DeliveryResult:
    text = _render_message(message)
    body = urlencode(
        {
            'chat_id': chat_id,
            'text': text,
            'link_preview_options': json.dumps({'is_disabled': True}, separators=(',', ':')),
        }
    ).encode('utf-8')
    request = Request(
        f'{_TELEGRAM_API}/bot{bot_token}/sendMessage',
        data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=max(int(timeout_seconds), 1)) as response:  # noqa: S310 - fixed Telegram API.
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        return DeliveryResult(False, f'Telegram rejected the request with HTTP {exc.code}.')
    except (URLError, TimeoutError, OSError, ValueError):
        return DeliveryResult(False, 'Telegram is unreachable or returned an invalid response.')

    if not isinstance(payload, dict) or not bool(payload.get('ok')):
        description = (
            str(payload.get('description') or 'Telegram rejected the message.')
            if isinstance(payload, dict)
            else 'Telegram rejected the message.'
        )
        return DeliveryResult(False, description[:500])
    raw_result = payload.get('result')
    result = raw_result if isinstance(raw_result, dict) else {}
    message_id = result.get('message_id')
    return DeliveryResult(True, 'Telegram message delivered.', str(message_id) if message_id is not None else None)


def _render_message(message: NotificationMessage) -> str:
    severity = str(message.severity or 'info').upper()
    content = '\n'.join(
        line for line in [f'KAORI · {severity}', message.title, '', message.body] if line is not None
    ).strip()
    if not message.action_url:
        return content[:_TELEGRAM_TEXT_LIMIT]

    action_label = message.action_label or 'Open KAORI'
    action = f'{action_label}: {message.action_url}'
    separator = '\n\n'
    content_limit = max(_TELEGRAM_TEXT_LIMIT - len(separator) - len(action), 0)
    if len(content) > content_limit:
        content = _truncate(content, content_limit)
    rendered = f'{content}{separator}{action}' if content else action
    return rendered[:_TELEGRAM_TEXT_LIMIT]


def _truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ''
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return f'{value[: limit - 1].rstrip()}…'


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = credential_map(existing)
    token = str(form.get('bot_token') or '').strip()
    destination = str(form.get('target_chat_id') or '').strip()
    return destination, {'bot_token': token or existing_credentials.get('bot_token', '')}, {}, bool(token)


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors: list[str] = []
    if not data.credentials.get('bot_token'):
        errors.append('Telegram bot token is required.')
    if not data.destination:
        errors.append('Telegram chat ID or @channel username is required.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    return {'target_chat_id': channel.destination}
