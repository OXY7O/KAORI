from __future__ import annotations

from typing import Any

from flask import url_for

from app.models.rbac import Role
from app.models.user import User
from app.notifications.service import record_operational_activity


def role_access_feedback(
    *,
    actor: User,
    event_type: str,
    status: str,
    title: str,
    message: str,
    role: Role | None = None,
    role_snapshot: dict[str, Any] | None = None,
    detail: str | None = None,
    queue_feedback: bool = True,
) -> dict[str, Any]:
    """Create the standard RBAC toast and Activity Audit record.

    ``role_snapshot`` is used for operations such as deletion where the ORM
    object is removed before the operational notification is persisted.
    """
    metadata: dict[str, Any] = {
        'module': 'rbac',
        'actor_id': actor.id,
        'actor_username': actor.username,
    }

    if role is not None:
        metadata.update(
            target_type='role',
            target_id=role.id,
            role_slug=role.name,
            role_display_name=role.display_name,
            role_type='default' if role.is_system else 'custom',
            lifecycle_status='active' if role.is_active else 'inactive',
            permission_count=len(role.permissions),
        )
    elif role_snapshot:
        metadata.update(role_snapshot)

    return record_operational_activity(
        user_id=actor.id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('settings.roles'),
        action_label='Open Roles & Access',
        action_icon='shield-check',
        metadata=metadata,
        queue_feedback=queue_feedback,
    )
