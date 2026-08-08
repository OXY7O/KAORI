from __future__ import annotations

from typing import Any

from flask import url_for

from app.models.user import User
from app.notifications.service import record_operational_activity


def user_management_feedback(
    *,
    actor: User,
    event_type: str,
    status: str,
    title: str,
    message: str,
    target: User | None = None,
    detail: str | None = None,
    queue_feedback: bool = True,
) -> dict[str, Any]:
    """Create canonical User Management feedback, inbox evidence, and Activity Audit."""
    metadata: dict[str, Any] = {
        'module': 'user_management',
        'actor_id': actor.id,
        'actor_username': actor.username,
    }
    if target is not None:
        metadata.update(
            target_type='user',
            target_id=target.id,
            target_username=target.username,
            identity_source=target.auth_source,
            lifecycle_status='deleted' if target.deleted_at else ('active' if target.account_is_active else 'inactive'),
            role=target.role_name,
            is_super_admin=target.is_super_admin,
        )

    return record_operational_activity(
        user_id=actor.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('users.index'),
        action_label='Open User Management',
        action_icon='users-round',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )
