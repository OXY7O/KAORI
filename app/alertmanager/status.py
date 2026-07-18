from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db
from app.models.alertmanager import AlertmanagerConfig, AlertmanagerInstance

AlertmanagerStatusSource = AlertmanagerInstance | AlertmanagerConfig


def mark_status(
    source: AlertmanagerStatusSource,
    *,
    status: str,
    error: str | None,
    response_time_ms: int | None,
    commit: bool = True,
) -> None:
    now = datetime.now(UTC)
    source.last_status = status
    source.last_error = error
    source.last_response_time_ms = response_time_ms
    source.last_checked_at = now
    source.updated_at = now
    if commit:
        db.session.commit()
