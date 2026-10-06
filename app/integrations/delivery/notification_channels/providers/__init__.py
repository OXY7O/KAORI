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
    setup_title: str
    setup_summary: str
    setup_requirements: tuple[str, ...]
    setup_steps: tuple[str, ...]
    security_note: str
    validation_note: str
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
        setup_title='Configure Telegram Bot Delivery',
        setup_summary=(
            'Use a dedicated Telegram bot and destination that KAORI can reach without sharing the bot token '
            'outside the channel credential boundary.'
        ),
        setup_requirements=(
            'A Telegram bot created with BotFather.',
            'The bot token generated for that bot.',
            'A target chat ID, group ID, or @channel username.',
            'Posting permission for the bot in the selected destination.',
        ),
        setup_steps=(
            'Create or select a dedicated KAORI notification bot in BotFather and copy its token.',
            'Add the bot to the intended chat, group, or channel and grant the minimum permission required '
            'to post messages.',
            'Resolve the destination as a numeric chat ID or @channel username, then enter it in the KAORI '
            'channel configuration.',
            'Save the channel and run Test Delivery. Keep the channel out of automatic use until the test '
            'status is Ready.',
        ),
        security_note=(
            'Treat the bot token as a secret. KAORI stores it in the channel credential payload and never renders '
            'the stored token back into the form.'
        ),
        validation_note='Test Delivery verifies both bot credentials and access to the configured destination.',
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
        setup_title='Configure SMTP Email Delivery',
        setup_summary=(
            'Connect KAORI to an internal relay or authenticated SMTP service, then define the sender identity '
            'and operational recipients.'
        ),
        setup_requirements=(
            'An SMTP host and port reachable from the KAORI worker runtime.',
            'STARTTLS, TLS/SMTPS, or an explicitly trusted relay policy.',
            'A sender email address and optional SMTP username/password.',
            'One or more recipient addresses for the operational audience.',
        ),
        setup_steps=(
            'Confirm the SMTP endpoint, port, and transport-security mode with the mail platform owner.',
            'Configure sender identity. If the relay requires authentication, enter the SMTP username and password.',
            'Add one or more recipients separated by commas and choose the KAORI domains and allowed uses for '
            'this channel.',
            'Save the channel and run Test Delivery. Verify the test message arrives before enabling the channel '
            'for automatic delivery.',
        ),
        security_note=(
            'STARTTLS is the recommended default. Store SMTP credentials only in the channel form; passwords are '
            'encrypted at rest and are not rendered back after save.'
        ),
        validation_note=(
            'Test Delivery proves SMTP connectivity, TLS negotiation, optional authentication, sender acceptance, '
            'and recipient delivery submission.'
        ),
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
        setup_title='Configure Microsoft Teams Workflow Delivery',
        setup_summary=(
            'Use a Teams Workflow / Power Automate webhook. Legacy Office 365 connector URLs are intentionally '
            'not accepted by the KAORI adapter.'
        ),
        setup_requirements=(
            'A Teams channel and a Workflow with “When a Teams webhook request is received”.',
            'The Workflow trigger configured for Anyone authentication for the current KAORI adapter.',
            'The HTTPS Workflow webhook URL from Power Automate.',
            'At least one additional Workflow co-owner for operational continuity.',
        ),
        setup_steps=(
            'Create the Workflow in the target Teams channel and use the Teams webhook request trigger.',
            'Configure the trigger for Anyone authentication. The current KAORI adapter does not send a bearer token.',
            'Copy the generated HTTPS webhook URL and enter a human-readable destination label in KAORI.',
            'Save the channel and run Test Delivery. Confirm the message reaches the intended Teams conversation '
            'before automatic use.',
        ),
        security_note=(
            'Treat the Workflow URL as a secret because possession of the URL can permit message submission. '
            'KAORI encrypts it at rest and never renders the stored URL back.'
        ),
        validation_note=(
            'Test Delivery verifies that the Workflow endpoint accepts the KAORI message payload with a successful '
            'HTTP response.'
        ),
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


def provider_catalog() -> list[dict[str, Any]]:
    return [
        {
            'key': adapter.key,
            'label': adapter.label,
            'icon': adapter.icon,
            'description': adapter.description,
            'transport': adapter.transport,
            'configuration': adapter.configuration,
            'setup_title': adapter.setup_title,
            'setup_summary': adapter.setup_summary,
            'setup_requirements': list(adapter.setup_requirements),
            'setup_steps': list(adapter.setup_steps),
            'security_note': adapter.security_note,
            'validation_note': adapter.validation_note,
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
