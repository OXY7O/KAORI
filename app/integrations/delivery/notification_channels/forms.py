from __future__ import annotations

from typing import Any

from app.integrations.delivery.notification_channels.catalog import domain_keys, event_type_keys
from app.integrations.delivery.notification_channels.contracts import NotificationChannelFormInput
from app.integrations.delivery.notification_channels.providers import get_notification_provider
from app.models.notification_channel import NotificationChannel


def parse_channel_form(
    form: Any,
    *,
    existing: NotificationChannel | None = None,
) -> NotificationChannelFormInput:
    provider_key = str(form.get('provider_key') or (existing.provider_key if existing else '')).strip().lower()
    minimum_severity = str(form.get('minimum_severity') or 'warning').strip().lower()
    supported_domains = set(domain_keys())
    supported_event_types = set(event_type_keys())
    domains = tuple(value for value in form.getlist('domains') if value in supported_domains)
    event_types = tuple(value for value in form.getlist('event_types') if value in supported_event_types)
    adapter = get_notification_provider(provider_key)
    destination, credentials, provider_config, credential_changed = (
        adapter.form_parser(form, existing) if adapter is not None else ('', {}, {}, False)
    )
    return NotificationChannelFormInput(
        name=str(form.get('name') or '').strip(),
        provider_key=provider_key,
        enabled=str(form.get('enabled') or '').lower() in {'1', 'true', 'yes', 'on'},
        destination=destination,
        credentials=credentials,
        provider_config=provider_config,
        minimum_severity=(minimum_severity if minimum_severity in {'critical', 'warning', 'info'} else 'warning'),
        domains=domains,
        event_types=event_types,
        credential_changed=credential_changed,
    )


def validate_channel_input(
    data: NotificationChannelFormInput,
    *,
    existing: NotificationChannel | None = None,
) -> list[str]:
    errors: list[str] = []
    if not data.name:
        errors.append('Channel name is required.')
    adapter = get_notification_provider(data.provider_key)
    if adapter is None:
        errors.append('Select a supported notification provider.')
        return errors
    if existing is not None and data.provider_key != existing.provider_key:
        errors.append('Notification provider cannot be changed. Create a new channel instead.')
        return errors
    if not data.domains:
        errors.append('Select at least one delivery domain for this notification channel.')
    if not data.event_types:
        errors.append('Select at least one allowed use for this notification channel.')
    errors.extend(adapter.form_validator(data))
    return errors


def get_channel_form_view(channel: NotificationChannel | None) -> dict[str, Any] | None:
    if channel is None:
        return None
    adapter = get_notification_provider(channel.provider_key)
    provider_view = adapter.form_view(channel) if adapter is not None else {}
    return {
        'id': channel.id,
        'name': channel.name,
        'provider_key': channel.provider_key,
        'enabled': channel.enabled,
        'minimum_severity': channel.minimum_severity,
        'domains': list(channel.domains or []),
        'event_types': list(channel.event_types or []),
        'credential_configured': bool(channel.credential_payload),
        **provider_view,
    }
