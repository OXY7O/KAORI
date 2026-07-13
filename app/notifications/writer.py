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
    notification = Notification(
        user_id=user_id,
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        metadata_json=metadata,
    )

    db.session.add(notification)
    db.session.commit()
    return notification
