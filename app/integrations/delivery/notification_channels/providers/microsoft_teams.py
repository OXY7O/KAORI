from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.form_support import credential_map
from app.models.notification_channel import NotificationChannel

_TEAMS_TEXT_LIMIT = 12000
_TEAMS_WORKFLOW_SUFFIXES = ('.environment.api.powerplatform.com', '.logic.azure.com')


def _is_approved_workflow_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = str(parsed.hostname or '').lower()
    return bool(
        parsed.scheme == 'https' and hostname and any(hostname.endswith(suffix) for suffix in _TEAMS_WORKFLOW_SUFFIXES)
    )


def send_microsoft_teams_message(
    *,
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int = 10,
) -> DeliveryResult:
    del destination, provider_config
    workflow_url = str(credentials.get('workflow_url') or '').strip()
    if not workflow_url:
        return DeliveryResult(False, 'Microsoft Teams Workflow webhook URL is not configured.')
    if not _is_approved_workflow_url(workflow_url):
        return DeliveryResult(False, 'Microsoft Teams Workflow webhook URL must use an approved HTTPS endpoint.')
    body = json.dumps({'text': _render_message(message)}, separators=(',', ':')).encode('utf-8')
    request = Request(
        workflow_url,
        data=body,
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(  # noqa: S310  # nosec B310
            request, timeout=max(int(timeout_seconds), 1)
        ) as response:
            status = int(getattr(response, 'status', 200) or 200)
    except HTTPError as exc:
        return DeliveryResult(False, f'Microsoft Teams Workflow rejected the request with HTTP {exc.code}.')
    except (URLError, TimeoutError, OSError, ValueError):
        return DeliveryResult(False, 'Microsoft Teams Workflow is unreachable or returned an invalid response.')
    if status < 200 or status >= 300:
        return DeliveryResult(False, f'Microsoft Teams Workflow returned HTTP {status}.')
    return DeliveryResult(True, 'Microsoft Teams Workflow accepted the message.')


def _render_message(message: NotificationMessage) -> str:
    lines = [f'KAORI · {str(message.severity or "info").upper()}', message.title, '', message.body]
    if message.action_url:
        lines.extend(['', f'{message.action_label or "Open KAORI"}: {message.action_url}'])
    return '\n'.join(lines).strip()[:_TEAMS_TEXT_LIMIT]


def parse_form(form: Any, existing: NotificationChannel | None) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = credential_map(existing)
    webhook_url = str(form.get('teams_workflow_url') or '').strip()
    destination = str(form.get('teams_destination') or '').strip()
    credentials = {'workflow_url': webhook_url or existing_credentials.get('workflow_url', '')}
    return destination, credentials, {'authentication_mode': 'anyone'}, bool(webhook_url)


def validate_form(data: NotificationChannelFormInput) -> list[str]:
    errors: list[str] = []
    if not data.destination:
        errors.append('Microsoft Teams destination label is required.')
    workflow_url = str(data.credentials.get('workflow_url') or '').strip()
    if not workflow_url:
        errors.append('Microsoft Teams Workflow webhook URL is required.')
        return errors
    parsed = urlparse(workflow_url)
    hostname = str(parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not hostname:
        errors.append('Microsoft Teams Workflow webhook URL must use HTTPS.')
    elif not any(hostname.endswith(suffix) for suffix in _TEAMS_WORKFLOW_SUFFIXES):
        errors.append('Use a Microsoft Teams Workflows / Power Automate webhook URL, not a legacy connector URL.')
    return errors


def form_view(channel: NotificationChannel) -> dict[str, Any]:
    return {'teams_destination': channel.destination}
