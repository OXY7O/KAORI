from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    title: str
    body: str
    severity: str
    action_url: str | None = None
    action_label: str | None = None
    content_format: str = 'plain_text'


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    success: bool
    message: str
    provider_message_id: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    event_type: str
    domain: str
    asset_type: str
    asset_key: str
    severity: str
    event_key: str
    message: NotificationMessage
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class NotificationChannelFormInput:
    name: str
    provider_key: str
    enabled: bool
    destination: str
    credentials: dict[str, str]
    provider_config: dict[str, object]
    minimum_severity: str
    domains: tuple[str, ...]
    event_types: tuple[str, ...]
    credential_changed: bool
