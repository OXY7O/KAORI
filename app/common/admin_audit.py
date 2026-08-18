from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.extensions.db import db
from app.models import AuditEvent, User

if TYPE_CHECKING:
    from app.models.rbac import Role


def record_admin_event(
    *,
    actor: User | None,
    action: str,
    target: User | Role,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist one Access administrative audit event in the caller's transaction."""

    event = AuditEvent()
    event.actor_user_id = actor.id if actor else None
    event.target_type = target.__class__.__name__.lower()
    event.target_id = str(target.id)
    event.action = action
    event.summary = summary
    event.metadata_json = metadata
    db.session.add(event)
