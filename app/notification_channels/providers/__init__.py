from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

from app.notification_channels.contracts import DeliveryResult, NotificationMessage
from app.notification_channels.providers.email import send_email_message
from app.notification_channels.providers.microsoft_teams import send_microsoft_teams_message
from app.notification_channels.providers.telegram import send_telegram_message

ProviderSender = Callable[
    [Mapping[str, str], str, Mapping[str, Any], NotificationMessage, int],
    DeliveryResult,
]


@dataclass(frozen=True, slots=True)
class NotificationProviderAdapter:
    key: str
    label: str
    icon: str
    description: str
    sender: ProviderSender


def _send_telegram(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    del provider_config
    token = str(credentials.get('bot_token') or '').strip()
    if not token:
        return DeliveryResult(False, 'Telegram bot token is not configured.')
    return send_telegram_message(
        bot_token=token,
        chat_id=destination,
        message=message,
        timeout_seconds=timeout_seconds,
    )


def _send_email(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    return send_email_message(
        credentials=credentials,
        destination=destination,
        provider_config=provider_config,
        message=message,
        timeout_seconds=timeout_seconds,
    )


def _send_microsoft_teams(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    return send_microsoft_teams_message(
        credentials=credentials,
        destination=destination,
        provider_config=provider_config,
        message=message,
        timeout_seconds=timeout_seconds,
    )


_PROVIDERS = {
    'telegram': NotificationProviderAdapter(
        key='telegram',
        label='Telegram',
        icon='message-circle',
        description='Telegram Bot API delivery to a chat, group, or channel.',
        sender=_send_telegram,
    ),
    'email': NotificationProviderAdapter(
        key='email',
        label='Email',
        icon='mail',
        description='SMTP delivery to one or more operational recipients.',
        sender=_send_email,
    ),
    'microsoft_teams': NotificationProviderAdapter(
        key='microsoft_teams',
        label='Microsoft Teams',
        icon='messages-square',
        description='Teams Workflows / Power Automate webhook delivery.',
        sender=_send_microsoft_teams,
    ),
}


def get_notification_provider(provider_key: str) -> NotificationProviderAdapter | None:
    return _PROVIDERS.get(str(provider_key or '').strip().lower())


def provider_labels() -> dict[str, str]:
    return {key: adapter.label for key, adapter in _PROVIDERS.items()}


def provider_catalog() -> list[dict[str, str]]:
    return [
        {
            'key': adapter.key,
            'label': adapter.label,
            'icon': adapter.icon,
            'description': adapter.description,
        }
        for adapter in _PROVIDERS.values()
    ]


__all__ = [
    'NotificationProviderAdapter',
    'get_notification_provider',
    'provider_catalog',
    'provider_labels',
]
