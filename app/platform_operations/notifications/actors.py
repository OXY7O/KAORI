from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import has_request_context
from flask_login import current_user

from app.models.user import User


@dataclass(frozen=True, slots=True)
class ActivityActorSnapshot:
    key: str
    actor_type: str
    user_id: int | None
    label: str
    email: str | None
    role: str
    auth_source: str

    def as_json(self) -> dict[str, Any]:
        return {
            'schema': 'activity_actor.v1',
            'key': self.key,
            'type': self.actor_type,
            'user_id': self.user_id,
            'label': self.label,
            'email': self.email,
            'role': self.role,
            'auth_source': self.auth_source,
        }


def actor_snapshot_for_user(user: User) -> ActivityActorSnapshot:
    return ActivityActorSnapshot(
        key=f'user:{user.id}',
        actor_type='user',
        user_id=int(user.id),
        label=user.display_label,
        email=user.email,
        role='Local Database Super Admin' if user.is_super_admin else user.role_display_name,
        auth_source=user.auth_source,
    )


def system_actor_snapshot() -> ActivityActorSnapshot:
    return ActivityActorSnapshot(
        key='system:kaori',
        actor_type='system',
        user_id=None,
        label='KAORI System',
        email=None,
        role='System Runtime',
        auth_source='internal',
    )


def unauthenticated_actor_snapshot() -> ActivityActorSnapshot:
    return ActivityActorSnapshot(
        key='unauthenticated',
        actor_type='unauthenticated',
        user_id=None,
        label='Unauthenticated Request',
        email=None,
        role='No Authenticated Role',
        auth_source='unauthenticated',
    )


def _user_by_id(value: object) -> User | None:
    try:
        user_id = int(str(value))
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None
    return User.query.filter(User.id == user_id).first()


def resolve_operational_actor(
    *,
    actor_user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> ActivityActorSnapshot:
    """Resolve immutable audit identity without treating notification recipient as actor."""

    explicit_user = _user_by_id(actor_user_id)
    if explicit_user is not None:
        return actor_snapshot_for_user(explicit_user)

    if has_request_context() and bool(getattr(current_user, 'is_authenticated', False)):
        request_user = _user_by_id(getattr(current_user, 'id', None))
        if request_user is not None:
            return actor_snapshot_for_user(request_user)

    event_metadata = metadata or {}
    for key in ('actor_user_id', 'requested_by_user_id', 'requested_by_id'):
        metadata_user = _user_by_id(event_metadata.get(key))
        if metadata_user is not None:
            return actor_snapshot_for_user(metadata_user)

    return system_actor_snapshot()
