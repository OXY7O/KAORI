from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.integrations.delivery.notification_channels.contracts import (
    DeliveryResult,
    NotificationChannelFormInput,
    NotificationMessage,
)
from app.integrations.delivery.notification_channels.providers.discord import (
    form_view as discord_form_view,
)
from app.integrations.delivery.notification_channels.providers.discord import (
    parse_form as parse_discord_form,
)
from app.integrations.delivery.notification_channels.providers.discord import (
    send_discord_message,
)
from app.integrations.delivery.notification_channels.providers.discord import (
    validate_form as validate_discord_form,
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
from app.integrations.delivery.notification_channels.providers.ntfy import (
    form_view as ntfy_form_view,
)
from app.integrations.delivery.notification_channels.providers.ntfy import (
    parse_form as parse_ntfy_form,
)
from app.integrations.delivery.notification_channels.providers.ntfy import (
    send_ntfy_message,
)
from app.integrations.delivery.notification_channels.providers.ntfy import (
    validate_form as validate_ntfy_form,
)
from app.integrations.delivery.notification_channels.providers.slack import (
    form_view as slack_form_view,
)
from app.integrations.delivery.notification_channels.providers.slack import (
    parse_form as parse_slack_form,
)
from app.integrations.delivery.notification_channels.providers.slack import (
    send_slack_message,
)
from app.integrations.delivery.notification_channels.providers.slack import (
    validate_form as validate_slack_form,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    form_view as telegram_form_view,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    normalize_telegram_topic_id,
    send_telegram_message,
)
from app.integrations.delivery.notification_channels.providers.telegram import (
    parse_form as parse_telegram_form,
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
    token = str(credentials.get('bot_token') or '').strip()
    if not token:
        return DeliveryResult(False, 'Telegram bot token is not configured.')
    raw_topic_id = provider_config.get('message_thread_id')
    topic_id = None
    if raw_topic_id is not None:
        topic_id = normalize_telegram_topic_id(raw_topic_id)
        if topic_id is None:
            return DeliveryResult(False, 'Telegram topic ID is invalid; delivery was not attempted.')
    return send_telegram_message(
        bot_token=token,
        chat_id=destination,
        message=message,
        timeout_seconds=timeout_seconds,
        message_thread_id=topic_id,
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


def _send_ntfy(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    return send_ntfy_message(
        credentials=credentials,
        destination=destination,
        provider_config=provider_config,
        message=message,
        timeout_seconds=timeout_seconds,
    )


def _send_slack(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    return send_slack_message(
        credentials=credentials,
        destination=destination,
        provider_config=provider_config,
        message=message,
        timeout_seconds=timeout_seconds,
    )


def _send_discord(
    credentials: Mapping[str, str],
    destination: str,
    provider_config: Mapping[str, Any],
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    return send_discord_message(
        credentials=credentials,
        destination=destination,
        provider_config=provider_config,
        message=message,
        timeout_seconds=timeout_seconds,
    )


_PROVIDERS = {
    'discord': NotificationProviderAdapter(
        key='discord',
        label='Discord',
        icon='messages-square',
        description='Channel-bound Discord Webhook delivery.',
        transport='HTTPS Webhook',
        configuration='Official Discord Webhook URL + human-readable destination label.',
        setup_title='Configure Discord Webhook Delivery',
        setup_summary='Send approved KAORI operational messages to an existing Discord channel.',
        setup_requirements=(
            'A Discord server with a channel where you can manage webhooks.',
            'An Execute Webhook URL generated for that channel.',
            'KAORI network access to the official Discord API over verified HTTPS.',
        ),
        setup_steps=(
            'In the Discord channel, create a webhook with the minimum posting permissions.',
            'Copy the secret Discord Webhook URL and give its target channel a recognizable label.',
            'Enter the channel label and secret URL into KAORI and choose allowed event/domain policies.',
            'Save and run Test Delivery; verify the alert appears only in the chosen channel.',
        ),
        security_note=(
            'Webhook URL is a secret and is stored encrypted. Official HTTPS Discord endpoint only, '
            'no redirects, no inherited proxy, and all user/role/everyone mentions disabled.'
        ),
        validation_note='Test Delivery checks acceptance by Discord, not human-read confirmation.',
        form_partial='integrations/delivery/notification_channels/providers/discord/_form.html',
        form_parser=parse_discord_form,
        form_validator=validate_discord_form,
        form_view=discord_form_view,
        sender=_send_discord,
    ),
    'slack': NotificationProviderAdapter(
        key='slack',
        label='Slack',
        icon='hash',
        description='Channel-bound Slack Incoming Webhook delivery.',
        transport='HTTPS Incoming Webhook',
        configuration='Approved Slack Incoming Webhook URL + human-readable destination label.',
        setup_title='Configure Slack Incoming Webhook',
        setup_summary='Send governed KAORI notifications to a selected Slack channel via its dedicated webhook.',
        setup_requirements=(
            'An authorized Slack workspace with an Incoming Webhook-enabled app.',
            'A channel-bound Incoming Webhook URL, stored as a secret in KAORI.',
            'Publishing permission for that app in the target Slack channel.',
        ),
        setup_steps=(
            'Create or configure a Slack app and enable Incoming Webhooks.',
            'Select the destination channel and copy its dedicated webhook URL.',
            'Enter the destination label and secret URL in KAORI, then select allowed event/domain policy.',
            'Save and run Test Delivery; confirm the message arrived in the expected Slack channel.',
        ),
        security_note=(
            'Incoming Webhook URL is a secret; it is encrypted and never rendered back. Only official HTTPS '
            'Slack webhook hosts and paths are allowed, redirects and inherited proxies are rejected.'
        ),
        validation_note='Test Delivery checks a Slack webhook acceptance response, not human message read status.',
        form_partial='integrations/delivery/notification_channels/providers/slack/_form.html',
        form_parser=parse_slack_form,
        form_validator=validate_slack_form,
        form_view=slack_form_view,
        sender=_send_slack,
    ),
    'ntfy': NotificationProviderAdapter(
        key='ntfy',
        label='ntfy',
        icon='bell-ring',
        description='Self-hosted topic-based mobile and web push.',
        transport='HTTPS Publish',
        configuration='Approved ntfy HTTPS origin + topic + optional access token.',
        setup_title='Configure ntfy Push Delivery',
        setup_summary='Connect KAORI to an approved self-managed ntfy server for governed topic publishing.',
        setup_requirements=(
            'An HTTPS ntfy server and publishing topic controlled by your operations team.',
            'Server origin explicitly approved via NOTIFICATION_NTFY_ALLOWED_ORIGINS.',
            'Valid server TLS certificate or approved CA bundle configured on the KAORI runtime.',
            'Optional ntfy access token with minimum publish rights.',
        ),
        setup_steps=(
            'Configure NOTIFICATION_NTFY_ALLOWED_ORIGINS on the KAORI application and worker; '
            'include only approved HTTPS origins, then restrict egress at network policy/firewall.',
            'If using internal PKI, configure NOTIFICATION_NTFY_CA_BUNDLE on the application and worker.',
            'Create a private ntfy topic and issue a publish-scoped access token where authorization is required.',
            'Set the server origin, topic, optional token and allowed KAORI event/domain policy.',
            'Save and run Test Delivery; confirm server acknowledgement and arrival on a test subscriber.',
        ),
        security_note=(
            'HTTPS is mandatory; no TLS bypass or arbitrary endpoints. Access tokens remain encrypted '
            'and hidden after saving. Network egress/DNS policy remains an operator-owned requirement.'
        ),
        validation_note='Test Delivery checks ntfy HTTPS publishing, not individual subscriber receipt.',
        form_partial='integrations/delivery/notification_channels/providers/ntfy/_form.html',
        form_parser=parse_ntfy_form,
        form_validator=validate_ntfy_form,
        form_view=ntfy_form_view,
        sender=_send_ntfy,
    ),
    'telegram': NotificationProviderAdapter(
        key='telegram',
        label='Telegram',
        icon='message-circle',
        description='Telegram Bot API delivery to a chat, supergroup topic, or channel.',
        transport='Bot API',
        configuration='Bot token + destination chat ID + optional forum topic ID.',
        setup_title='Configure Telegram Bot Delivery',
        setup_summary=(
            'Use a dedicated Telegram bot and destination that KAORI can reach without sharing the bot token '
            'outside the channel credential boundary.'
        ),
        setup_requirements=(
            'A Telegram bot created with BotFather.',
            'The bot token generated for that bot.',
            'A target chat ID, supergroup ID, or @channel username.',
            'For topic routing, enable Topics in a Telegram supergroup and obtain its numeric message_thread_id.',
            'Posting permission for the bot in the selected chat and topic.',
        ),
        setup_steps=(
            'Create or select a dedicated KAORI notification bot in BotFather and copy its token.',
            'Add the bot to the intended chat, group, or channel and grant the minimum permission required '
            'to post messages.',
            'Resolve the destination as a numeric chat/supergroup ID or @channel username. Optionally enter a '
            'numeric Topic ID for a supergroup forum topic.',
            'Create one KAORI Notification Channel per application delivery topic, then save and run Test '
            'Delivery to confirm the selected topic receives the message.',
            'GitHub Actions notifications remain owned by the separate GitHub notifier; avoid subscribing an '
            'application channel to duplicate that delivery.',
        ),
        security_note=(
            'Treat the bot token as a secret. KAORI stores it in the channel credential payload and never renders '
            'the stored token back into the form.'
        ),
        validation_note='Test Delivery confirms bot access to the configured chat and optional forum topic.',
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
