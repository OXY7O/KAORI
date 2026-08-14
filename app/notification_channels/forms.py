from __future__ import annotations

from email.utils import getaddresses
from typing import Any
from urllib.parse import urlparse

from app.models.notification_channel import NotificationChannel
from app.notification_channels.contracts import NotificationChannelFormInput

_SUPPORTED_PROVIDERS = {'telegram', 'email', 'microsoft_teams'}
_TEAMS_WORKFLOW_SUFFIXES = ('.environment.api.powerplatform.com', '.logic.azure.com')
_EMAIL_SECURITY_MODES = {'starttls', 'tls', 'none'}
_SUPPORTED_EVENT_TYPES = {'alert_intelligence.active_alert', 'report.generated'}


def parse_channel_form(
    form: Any,
    *,
    existing: NotificationChannel | None = None,
) -> NotificationChannelFormInput:
    provider_key = str(
        form.get('provider_key') or (existing.provider_key if existing else 'telegram')
    ).strip().lower()
    minimum_severity = str(form.get('minimum_severity') or 'warning').strip().lower()
    domains = tuple(
        value for value in form.getlist('domains') if value in {'kubernetes', 'object_storage'}
    ) or ('kubernetes', 'object_storage')
    event_types = tuple(value for value in form.getlist('event_types') if value in _SUPPORTED_EVENT_TYPES)
    destination, credentials, provider_config, credential_changed = _parse_provider_payload(
        provider_key, form, existing
    )
    return NotificationChannelFormInput(
        name=str(form.get('name') or '').strip(),
        provider_key=provider_key,
        enabled=str(form.get('enabled') or '').lower() in {'1', 'true', 'yes', 'on'},
        destination=destination,
        credentials=credentials,
        provider_config=provider_config,
        minimum_severity=(
            minimum_severity if minimum_severity in {'critical', 'warning', 'info'} else 'warning'
        ),
        domains=domains,
        event_types=event_types,
        credential_changed=credential_changed,
    )


def _parse_provider_payload(
    provider_key: str,
    form: Any,
    existing: NotificationChannel | None,
) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    parsers = {
        'telegram': _parse_telegram_payload,
        'email': _parse_email_payload,
        'microsoft_teams': _parse_teams_payload,
    }
    parser = parsers.get(provider_key)
    if parser is None:
        return '', {}, {}, False
    return parser(form, existing)


def _parse_telegram_payload(
    form: Any, existing: NotificationChannel | None
) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = _credential_map(existing)
    token = str(form.get('bot_token') or '').strip()
    destination = str(form.get('target_chat_id') or '').strip()
    return destination, {'bot_token': token or existing_credentials.get('bot_token', '')}, {}, bool(token)


def _parse_email_payload(
    form: Any, existing: NotificationChannel | None
) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = _credential_map(existing)
    username = str(form.get('smtp_username') or '').strip()
    password = str(form.get('smtp_password') or '').strip()
    existing_username = str((existing.provider_config or {}).get('smtp_username') or '') if existing else ''
    clear_password = existing is not None and bool(existing_username) and not username
    credentials = {
        'password': '' if clear_password else (password or existing_credentials.get('password', ''))
    }
    provider_config = {
        'smtp_host': str(form.get('smtp_host') or '').strip(),
        'smtp_port': _positive_int(form.get('smtp_port'), default=587),
        'smtp_security': str(form.get('smtp_security') or 'starttls').strip().lower(),
        'smtp_username': username,
        'sender_email': str(form.get('sender_email') or '').strip(),
        'sender_name': str(form.get('sender_name') or 'KAORI').strip() or 'KAORI',
    }
    destination = str(form.get('email_recipients') or '').strip()
    return destination, credentials, provider_config, bool(password) or clear_password


def _parse_teams_payload(
    form: Any, existing: NotificationChannel | None
) -> tuple[str, dict[str, str], dict[str, Any], bool]:
    existing_credentials = _credential_map(existing)
    webhook_url = str(form.get('teams_workflow_url') or '').strip()
    destination = str(form.get('teams_destination') or '').strip()
    credentials = {'workflow_url': webhook_url or existing_credentials.get('workflow_url', '')}
    return destination, credentials, {'authentication_mode': 'anyone'}, bool(webhook_url)

def validate_channel_input(
    data: NotificationChannelFormInput,
    *,
    existing: NotificationChannel | None = None,
) -> list[str]:
    errors: list[str] = []
    if not data.name:
        errors.append('Channel name is required.')
    if data.provider_key not in _SUPPORTED_PROVIDERS:
        errors.append('Unsupported notification provider.')
        return errors
    if existing is not None and data.provider_key != existing.provider_key:
        errors.append('Notification provider cannot be changed. Create a new channel instead.')
        return errors
    if not data.event_types:
        errors.append('Select at least one allowed use for this notification channel.')

    if data.provider_key == 'telegram':
        if not data.credentials.get('bot_token'):
            errors.append('Telegram bot token is required.')
        if not data.destination:
            errors.append('Telegram chat ID or @channel username is required.')
    elif data.provider_key == 'email':
        errors.extend(_validate_email(data))
    elif data.provider_key == 'microsoft_teams':
        errors.extend(_validate_teams(data))
    return errors


def get_channel_form_view(channel: NotificationChannel | None) -> dict[str, Any] | None:
    if channel is None:
        return None
    config = dict(channel.provider_config or {})
    return {
        'id': channel.id,
        'name': channel.name,
        'provider_key': channel.provider_key,
        'enabled': channel.enabled,
        'minimum_severity': channel.minimum_severity,
        'domains': list(channel.domains or []),
        'event_types': list(channel.event_types or []),
        'credential_configured': bool(channel.credential_payload),
        'target_chat_id': channel.destination if channel.provider_key == 'telegram' else '',
        'email_recipients': channel.destination if channel.provider_key == 'email' else '',
        'smtp_host': str(config.get('smtp_host') or ''),
        'smtp_port': int(config.get('smtp_port') or 587),
        'smtp_security': str(config.get('smtp_security') or 'starttls'),
        'smtp_username': str(config.get('smtp_username') or ''),
        'sender_email': str(config.get('sender_email') or ''),
        'sender_name': str(config.get('sender_name') or 'KAORI'),
        'teams_destination': channel.destination if channel.provider_key == 'microsoft_teams' else '',
    }


def _validate_email(data: NotificationChannelFormInput) -> list[str]:
    errors: list[str] = []
    config = data.provider_config
    if not str(config.get('smtp_host') or '').strip():
        errors.append('SMTP host is required.')
    port = int(config.get('smtp_port') or 0)
    if port < 1 or port > 65535:
        errors.append('SMTP port must be between 1 and 65535.')
    if config.get('smtp_security') not in _EMAIL_SECURITY_MODES:
        errors.append('SMTP security mode must be STARTTLS, TLS, or None.')
    sender_email = str(config.get('sender_email') or '').strip()
    if not _valid_email_address(sender_email):
        errors.append('A valid sender email address is required.')
    recipients = [address for _, address in getaddresses([data.destination]) if address]
    if not recipients or any(not _valid_email_address(address) for address in recipients):
        errors.append('At least one valid recipient email address is required.')
    username = str(config.get('smtp_username') or '').strip()
    password = str(data.credentials.get('password') or '')
    if username and not password:
        errors.append('SMTP password is required when SMTP username is configured.')
    return errors


def _validate_teams(data: NotificationChannelFormInput) -> list[str]:
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


def _valid_email_address(value: str) -> bool:
    local, separator, domain = value.rpartition('@')
    return bool(local and separator and domain and '.' in domain and ' ' not in value)


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _credential_map(channel: NotificationChannel | None) -> dict[str, str]:
    if channel is None:
        return {}
    import json

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
