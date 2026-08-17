from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.email import (
    form_view as email_form_view,
)
from app.integrations.delivery.notification_channels.providers.email import (
    parse_form as parse_email_form,
)
from app.integrations.delivery.notification_channels.providers.email import (
    send_email_message,
)
from app.integrations.delivery.notification_channels.providers.email import (
    validate_form as validate_email_form,
)
from app.integrations.delivery.notification_channels.providers.microsoft_teams import (
    form_view as microsoft_teams_form_view,
)
from app.integrations.delivery.notification_channels.providers.microsoft_teams import (
    parse_form as parse_microsoft_teams_form,
)
from app.integrations.delivery.notification_channels.providers.microsoft_teams import (
    send_microsoft_teams_message,
)
from app.integrations.delivery.notification_channels.providers.microsoft_teams import (
    validate_form as validate_microsoft_teams_form,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    form_view as telegram_form_view,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    parse_form as parse_telegram_form,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    send_telegram_message,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    validate_form as validate_telegram_form,
)
from app.models.notification_channel import NotificationChannel

ProviderSender = Callable[
    [Mapping[str, str], str, Mapping[str, Any], NotificationMessage, int],
    DeliveryResult,
]
ProviderFormParser = Callable[
    [Any, NotificationChannel | None],
    tuple[str, dict[str, str], dict[str, Any], bool],
]
ProviderFormValidator = Callable[[NotificationChannelFormInput], list[str]]
ProviderFormView = Callable[[NotificationChannel], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class NotificationProviderAdapter:
    key: str
    label: str
    icon: str
    description: str
    transport: str
    configuration: str
    form_partial: str
    form_parser: ProviderFormParser
    form_validator: ProviderFormValidator
    form_view: ProviderFormView
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
        transport='Bot API',
        configuration='Bot token + chat, group, or channel destination.',
        form_partial='integrations/delivery/notification_channels/providers/telegram/_form.html',
        form_parser=parse_telegram_form,
        form_validator=validate_telegram_form,
        form_view=telegram_form_view,
        sender=_send_telegram,
    ),
    'email': NotificationProviderAdapter(
        key='email',
        label='Email',
        icon='mail',
        description='SMTP delivery to one or more operational recipients.',
        transport='SMTP',
        configuration='SMTP server + sender identity + one or more recipients.',
        form_partial='integrations/delivery/notification_channels/providers/email/_form.html',
        form_parser=parse_email_form,
        form_validator=validate_email_form,
        form_view=email_form_view,
        sender=_send_email,
    ),
    'microsoft_teams': NotificationProviderAdapter(
        key='microsoft_teams',
        label='Microsoft Teams',
        icon='messages-square',
        description='Teams Workflows / Power Automate webhook delivery.',
        transport='Teams Workflows',
        configuration='Power Automate webhook URL + human-readable Teams destination label.',
        form_partial='integrations/delivery/notification_channels/providers/microsoft_teams/_form.html',
        form_parser=parse_microsoft_teams_form,
        form_validator=validate_microsoft_teams_form,
        form_view=microsoft_teams_form_view,
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
            'transport': adapter.transport,
            'configuration': adapter.configuration,
            'form_partial': adapter.form_partial,
        }
        for adapter in _PROVIDERS.values()
    ]


__all__ = [
    'NotificationProviderAdapter',
    'get_notification_provider',
    'provider_catalog',
    'provider_labels',
]
