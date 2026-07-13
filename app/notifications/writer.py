from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models.notification import Notification


def persist_notification(
    *,
    user_id: int,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
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
    notification.status = status
    notification.title = title
    notification.message = message
    notification.detail = detail
    notification.action_url = action_url
    notification.metadata_json = metadata

    db.session.add(notification)
    db.session.commit()
    return notification
