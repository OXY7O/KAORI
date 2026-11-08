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
    configuration_guide_summary: str
    configuration_guide_items: tuple[str, ...]
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
            'Create a Discord channel webhook with only the minimum posting permissions required for KAORI delivery.',
            'Copy its secret Execute Webhook URL and label the intended destination channel clearly.',
            'Enter the label and secret URL in KAORI, then restrict allowed events and delivery domains.',
            'Save and run Test Delivery; verify the test alert appears only in the selected Discord channel.',
        ),
        security_note=(
            'Encrypt webhook URLs; require official Discord HTTPS, block redirects/proxies, and suppress '
            'all mass mentions.'
        ),
        validation_note=("Test Delivery verifies Discord webhook acceptance, not a recipient's read confirmation."),
        configuration_guide_summary=('Identify the Discord destination and supply its channel-bound webhook securely.'),
        configuration_guide_items=(
            'Destination Label: Human-readable name; the webhook decides which Discord channel receives messages.',
            'Discord Webhook URL: Encrypted secret; mass mentions disabled on every message.',
        ),
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
            'Create or select a Slack app, enable Incoming Webhooks, and authorize it in the intended workspace.',
            'Choose the destination channel and copy its dedicated, channel-bound Incoming Webhook URL.',
            'Enter the destination label and secret URL in KAORI, then restrict allowed events and delivery domains.',
            'Save and run Test Delivery; confirm webhook acceptance and arrival in the selected Slack channel.',
        ),
        security_note=(
            'Encrypt Slack webhook URLs; allow official HTTPS hosts/paths only, with no redirects or inherited proxies.'
        ),
        validation_note=("Test Delivery verifies Slack webhook acceptance, not a recipient's read confirmation."),
        configuration_guide_summary=('Label the Slack destination and use the approved channel-bound webhook URL.'),
        configuration_guide_items=(
            'Destination Label: Reference only; the webhook URL owns the Slack channel binding.',
            'Incoming Webhook URL: Encrypted secret. Channel-bound official Slack URL; never rendered back.',
        ),
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
            'Allow ntfy HTTPS origins via NOTIFICATION_NTFY_ALLOWED_ORIGINS (app/worker); restrict egress.',
            'For internal PKI, configure NOTIFICATION_NTFY_CA_BUNDLE consistently on the application and worker.',
            'Create a private ntfy topic and issue a publish-scoped access token when authorization is required.',
            'Enter the approved server origin, topic, optional token, and permitted KAORI event/domain policy.',
            'Save and run Test Delivery; confirm server acknowledgement and arrival on a test subscriber.',
        ),
        security_note=(
            'Require approved HTTPS and verified TLS with no bypass; encrypt tokens and enforce '
            'DNS/network egress policy.'
        ),
        validation_note=('Test Delivery verifies ntfy HTTPS publish acceptance, not individual subscriber receipt.'),
        configuration_guide_summary=(
            'Use an approved HTTPS origin and private topic, with a publish token when needed.'
        ),
        configuration_guide_items=(
            'ntfy HTTPS Server: Must match an origin allowed by NOTIFICATION_NTFY_ALLOWED_ORIGINS.',
            'Topic: Approved private topic name; do not put secrets in the topic.',
            'Access Token: Encrypted and never rendered after saving. Test Delivery verifies publishing to the '
            'chosen topic.',
        ),
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
        setup_summary='Use a dedicated Telegram bot and destination; keep its token encrypted in KAORI.',
        setup_requirements=(
            'A Telegram bot created with BotFather.',
            'The bot token generated for that bot.',
            'A target chat ID, supergroup ID, or @channel username.',
            'For topic routing, enable Topics in a Telegram supergroup and obtain its numeric message_thread_id.',
            'Posting permission for the bot in the selected chat and topic.',
        ),
        setup_steps=(
            'Create or select a dedicated KAORI Telegram bot in BotFather and copy its secret bot token.',
            'Add the bot to the intended chat, group, or channel with minimum required posting permissions.',
            'Use a numeric chat/supergroup ID or @channel username; add an optional numeric Topic '
            'ID for forum routing.',
            'Create one KAORI channel per application delivery topic, then test delivery to the chosen topic.',
            'Keep GitHub Actions notifications on the separate GitHub notifier to avoid duplicate '
            'application delivery.',
        ),
        security_note=(
            'Encrypt Telegram bot tokens as channel secrets; never redisplay saved credentials after setup.'
        ),
        validation_note=(
            'Test Delivery verifies bot posting access to the selected chat/topic, not a human read receipt.'
        ),
        configuration_guide_summary=('Configure the bot credential and destination; a forum topic is optional.'),
        configuration_guide_items=(
            'Bot Token: Stored as a secret and never rendered back after save.',
            'Chat ID / @Channel: The bot must already be able to post to this destination.',
            'Telegram Topic ID: Numeric Telegram message_thread_id of a Forum Topic in your supergroup.',
            'Leave blank for ordinary chat delivery. Changing this requires a new Test Delivery.',
        ),
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
        setup_summary='Use an approved SMTP relay, sender identity, and operational recipients.',
        setup_requirements=(
            'An SMTP host and port reachable from the KAORI worker runtime.',
            'STARTTLS, TLS/SMTPS, or an explicitly trusted relay policy.',
            'A sender email address and optional SMTP username/password.',
            'One or more recipient addresses for the operational audience.',
        ),
        setup_steps=(
            'Confirm SMTP host, port, and transport security with the mail platform owner before configuration.',
            'Set the sender identity and, when required, enter the SMTP username and secret password.',
            'Enter comma-separated recipients, then choose allowed KAORI delivery domains and event types.',
            'Save and run Test Delivery; verify test message arrival before enabling automatic delivery.',
        ),
        security_note=(
            'Use STARTTLS, TLS/SMTPS or an approved trusted relay; encrypt SMTP passwords and never redisplay them.'
        ),
        validation_note=(
            'Test Delivery checks SMTP security, authentication, sender acceptance, and recipient '
            'submission; not reading.'
        ),
        configuration_guide_summary=('Configure SMTP transport, credentials, sender identity, and the recipient list.'),
        configuration_guide_items=(
            'SMTP Host / Port / Transport Security: Use a reachable SMTP server and the approved STARTTLS, '
            'TLS/SMTPS, or trusted relay policy.',
            'SMTP Username / Password: Provide credentials when required; the password is stored encrypted and '
            'is not rendered after save.',
            'Sender Name / Email: Enter the approved sender identity for the SMTP relay.',
            'Recipients: Separate multiple recipients with commas.',
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
        setup_summary='Use a Teams Workflow webhook; legacy Office 365 connector URLs are unsupported.',
        setup_requirements=(
            'A Teams channel and a Workflow with “When a Teams webhook request is received”.',
            'The Workflow trigger configured for Anyone authentication for the current KAORI adapter.',
            'The HTTPS Workflow webhook URL from Power Automate.',
            'At least one additional Workflow co-owner for operational continuity.',
        ),
        setup_steps=(
            'Create a Teams Workflow in the intended channel using the Teams webhook request trigger.',
            'Set trigger authentication to Anyone; the current KAORI adapter does not submit a bearer token.',
            'Copy the HTTPS Workflow URL and enter a recognizable destination label into KAORI.',
            'Save and run Test Delivery; confirm the intended Teams conversation receives the '
            'message before automatic use.',
        ),
        security_note=(
            'Encrypt the Teams Workflow URL as a secret; possession permits posting, so never redisplay the saved URL.'
        ),
        validation_note=(
            "Test Delivery confirms the Teams Workflow accepts KAORI's payload over HTTPS, not a read receipt."
        ),
        configuration_guide_summary=(
            'Identify the Teams destination and use a qualified Power Automate Workflow endpoint.'
        ),
        configuration_guide_items=(
            'Destination Label: Human-readable Teams channel or workflow destination.',
            'Workflow Webhook URL: Use a Teams Workflow / Power Automate URL, not legacy Office 365 connector '
            'webhook URLs.',
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
            'configuration_guide_summary': adapter.configuration_guide_summary,
            'configuration_guide_items': list(adapter.configuration_guide_items),
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
