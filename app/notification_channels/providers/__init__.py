from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable

from app.notification_channels.contracts import DeliveryResult, NotificationMessage
from app.notification_channels.providers.telegram import send_telegram_message

ProviderSender = Callable[[Mapping[str, str], str, NotificationMessage, int], DeliveryResult]


@dataclass(frozen=True, slots=True)
class NotificationProviderAdapter:
    key: str
    label: str
    sender: ProviderSender


def _send_telegram(
    credentials: Mapping[str, str],
    destination: str,
    message: NotificationMessage,
    timeout_seconds: int,
) -> DeliveryResult:
    token = str(credentials.get('bot_token') or '').strip()
    if not token:
        return DeliveryResult(False, 'Telegram bot token is not configured.')
    return send_telegram_message(
        bot_token=token,
        chat_id=destination,
        message=message,
        timeout_seconds=timeout_seconds,
    )


_PROVIDERS = {
    'telegram': NotificationProviderAdapter(
        key='telegram',
        label='Telegram',
        sender=_send_telegram,
    ),
}


def get_notification_provider(provider_key: str) -> NotificationProviderAdapter | None:
    return _PROVIDERS.get(str(provider_key or '').strip().lower())


def provider_labels() -> dict[str, str]:
    return {key: adapter.label for key, adapter in _PROVIDERS.items()}


__all__ = ['NotificationProviderAdapter', 'get_notification_provider', 'provider_labels']
