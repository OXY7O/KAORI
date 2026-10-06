from __future__ import annotations

from typing import Any

from flask import url_for

from app.models.user import User
from app.platform_operations.notifications.service import record_operational_activity


def identity_provider_feedback(
    *,
    actor: User,
    event_type: str,
    status: str,
    title: str,
    message: str,
    provider_id: int | None = None,
    provider_key: str | None = None,
    queue_feedback: bool = True,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        'module': 'identity_providers',
        'actor_id': actor.id,
        'actor_username': actor.username,
    }
    if provider_id is not None:
        metadata['provider_id'] = provider_id
    if provider_key:
        metadata['provider_key'] = provider_key
    return record_operational_activity(
        user_id=actor.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        action_url=url_for('identity_providers.index'),
        action_label='Open Identity Providers',
        action_icon='fingerprint',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )
