from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.notification_channels.contracts import DeliveryResult, NotificationMessage

_TEAMS_TEXT_LIMIT = 12000


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
    body = json.dumps({'text': _render_message(message)}, separators=(',', ':')).encode('utf-8')
    request = Request(
        workflow_url,
        data=body,
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=max(int(timeout_seconds), 1)) as response:  # noqa: S310 - validated Microsoft endpoint.
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
