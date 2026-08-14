from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    title: str
    body: str
    severity: str
    action_url: str | None = None
    action_label: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    success: bool
    message: str
    provider_message_id: str | None = None
