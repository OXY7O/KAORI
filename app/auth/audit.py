from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import request
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models.auth import AuthLoginEvent


def record_login_attempt(
    *,
    username: str,
    source: str,
    success: bool,
    reason: str,
    user_id: int | None = None,
) -> None:
    event = AuthLoginEvent()
    event.username = username.strip() or None
    event.user_id = user_id
    event.source = source
    event.success = success
    event.reason = reason
    event.ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    event.user_agent = request.headers.get('User-Agent')

    try:
        db.session.add(event)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()


def build_login_audit_cutoff(retention_days: int) -> datetime:
    """Return the UTC cutoff timestamp for login audit retention cleanup."""

    return datetime.now(UTC) - timedelta(days=retention_days)


def count_login_audit_events_older_than(retention_days: int) -> int:
    cutoff = build_login_audit_cutoff(retention_days)

    return AuthLoginEvent.query.filter(
        AuthLoginEvent.created_at < cutoff,
    ).count()


def cleanup_login_audit_events(retention_days: int) -> int:
    cutoff = build_login_audit_cutoff(retention_days)

    deleted_count = AuthLoginEvent.query.filter(
        AuthLoginEvent.created_at < cutoff,
    ).delete(
        synchronize_session=False,
    )
    db.session.commit()

    return int(deleted_count or 0)
