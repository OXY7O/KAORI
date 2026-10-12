from __future__ import annotations

import json
import os
import re
import ssl
from collections.abc import Mapping
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
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

_TOPIC = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
_BODY_LIMIT = 4096


def _origin(value: str) -> str | None:
    """Accept one complete HTTPS origin; never a URL carrying query or credentials."""
    if not value or value != value.strip() or any(ord(c) < 33 or ord(c) == 127 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.port is None and ':' in parsed.netloc
        ):
            return None
        port = parsed.port
    except ValueError:
        return None
    if port is not None and (port < 1 or port > 65535):
        return None
    hostname = parsed.hostname.lower()
    if hostname.endswith('.') or '%' in hostname or '\\' in hostname or not hostname.isascii():
        return None
    # urlsplit normalizes host case; retain an explicit port when approved.
    return 'https://' + hostname + (f':{port}' if port is not None and port != 443 else '')


def _approved_origin(value: str) -> str | None:
    origin = _origin(value)
    if origin is None:
        return None
    approved = {
        normalized
        for entry in os.getenv('NOTIFICATION_NTFY_ALLOWED_ORIGINS', '').split(',')
        if (normalized := _origin(entry.strip())) is not None
    }
    return origin if origin in approved else None


def _valid_topic(value: str) -> bool:
    return bool(_TOPIC.fullmatch(value))


def _header_value(value: str, *, limit: int) -> str:
    return ''.join(ch if 32 <= ord(ch) < 127 else ' ' for ch in value).strip()[:limit]


def send_ntfy_message(
    *,
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int = 10,
) -> DeliveryResult:
    endpoint = _approved_origin(str(provider_config.get('base_url') or ''))
    if endpoint is None or not _valid_topic(destination):
        return DeliveryResult(False, 'ntfy endpoint/topic is not approved for delivery.')
    token = str(credentials.get('access_token') or '')
    if '\r' in token or '\n' in token:
        return DeliveryResult(False, 'ntfy access token is invalid.')
    header = {
        'Content-Type': 'text/plain; charset=utf-8',
        'X-Title': _header_value(f'KAORI · {message.title}', limit=160),
        'X-Priority': {'critical': '5', 'warning': '4'}.get(message.severity.lower(), '3'),
    }
    if token:
        header['Authorization'] = f'Bearer {token}'
    if message.action_url:
        link = urlsplit(message.action_url)
        if link.scheme in {'http', 'https'} and link.hostname and not link.username:
            header['X-Click'] = message.action_url[:1000]
    body = unescape(message.body) if message.content_format == 'html' else message.body
    body = body.strip()[:_BODY_LIMIT]
    request = Request(
        f'{endpoint}/{quote(destination, safe="")}',
        data=body.encode('utf-8'),
        headers=header,
        method='POST',
    )
    try:
        ca_path = os.getenv('NOTIFICATION_NTFY_CA_BUNDLE', '').strip()
        context = ssl.create_default_context(cafile=ca_path or None)
        # Never inherit HTTP_PROXY/HTTPS_PROXY; require an operator-approved
        # origin and network-layer egress controls for self-managed endpoints.
        with build_opener(ProxyHandler({}), HTTPSHandler(context=context), DenyRedirects()).open(
            request, timeout=max(int(timeout_seconds), 1),
        ) as response:
            status = int(getattr(response, 'status', 200) or 200)
            raw = response.read(16384)
    except HTTPError as exc:
        return DeliveryResult(False, f'ntfy rejected delivery with HTTP {exc.code}.')
    except (URLError, OSError, TimeoutError, ValueError, ssl.SSLError):
        return DeliveryResult(False, 'ntfy endpoint is unreachable or TLS verification failed.')
    if not 200 <= status < 300:
        return DeliveryResult(False, f'ntfy endpoint returned HTTP {status}.')
    try:
        parsed_result = json.loads(raw)
        if not isinstance(parsed_result, dict) or not isinstance(parsed_result.get('id'), str):
            raise ValueError('Invalid provider acknowledgement')
    except (ValueError, TypeError):
        return DeliveryResult(False, 'ntfy returned an invalid publish acknowledgement.')
    return DeliveryResult(True, 'ntfy accepted the published message.', parsed_result['id'][:120])


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    saved = credential_map(existing)
    token = str(form.get('ntfy_access_token') or '').strip()
    return (
        str(form.get('ntfy_topic') or '').strip(),
        {'access_token': token or saved.get('access_token', '')},
        {'base_url': str(form.get('ntfy_base_url') or '').strip()},
        bool(token),
    )


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors = []
    if not _valid_topic(data.destination):
        errors.append('ntfy topic must contain 1–64 letters, digits, underscores or hyphens.')
    if _approved_origin(str(data.provider_config.get('base_url') or '')) is None:
        errors.append('ntfy HTTPS server must match a configured approved origin.')
    if '\r' in data.credentials.get('access_token', '') or '\n' in data.credentials.get('access_token', ''):
        errors.append('ntfy access token contains invalid characters.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    return {
        'ntfy_topic': channel.destination,
        'ntfy_base_url': str((channel.provider_config or {}).get('base_url') or ''),
    }
