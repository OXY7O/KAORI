from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.models.notification import Notification
from app.notifications.actors import ActivityActorSnapshot
from app.notifications.event_catalog import event_category_key


@dataclass(frozen=True, slots=True)
class NotificationPersistenceEvidence:
    metadata: dict[str, Any] | None
    actor: ActivityActorSnapshot


def persist_notification(
    *,
    user_id: int | None,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    evidence: NotificationPersistenceEvidence,
    deck_visible: bool = True,
) -> Notification:
    """Persist one already-normalized notification record.

    Business rules, normalization, retry handling, and user feedback belong to
    ``service.py``. This module intentionally owns database persistence only.
    """
    # Assign mapped attributes explicitly. Flask-SQLAlchemy provides a dynamic
    # keyword constructor at runtime, but static analyzers cannot reliably infer
    # that constructor signature from the declarative model.
    notification = Notification()
    notification.user_id = user_id
    notification.event_type = event_type
    notification.category_key = event_category_key(event_type)
    notification.actor_key = evidence.actor.key
    notification.actor_label = evidence.actor.label
    notification.actor_snapshot_json = evidence.actor.as_json()
    notification.status = status
    notification.title = title
    notification.message = message
    notification.detail = detail
    notification.action_url = action_url
    notification.metadata_json = evidence.metadata
    notification.deck_visible = bool(deck_visible)
    if not notification.deck_visible:
        notification.read_at = datetime.now(UTC)

    db.session.add(notification)
    db.session.commit()
    return notification
