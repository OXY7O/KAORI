from __future__ import annotations

from typing import Literal

from app.models import Notification
from app.models.authentication_security import AuthenticationMfaFactor


def recent_authentication_events(user_id: int, *, limit: int = 5) -> list[Notification]:
    return (
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.event_type == 'authentication',
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


AuthenticationEventKind = Literal['success', 'failed', 'sign_out', 'expired', 'unknown']


def authentication_event_kind(event: Notification) -> AuthenticationEventKind:
    """Classify committed authentication evidence without assuming a sign-in."""
    metadata = event.metadata_json or {}
    action = metadata.get('access_action')
    if action is None or action == '':
        # Only recognize exact historical titles emitted by the audit producer.
        action = {
            'User signed out': 'logout',
            'User signed in': 'login',
            'Sign-in attempt failed': 'login',
        }.get(event.title)
    if action == 'session_expired' and event.status == 'warning':
        return 'expired'
    if action == 'logout' and event.status == 'success':
        return 'sign_out'
    if action == 'login':
        if event.status == 'success':
            return 'success'
        if event.status == 'error':
            return 'failed'
    return 'unknown'


def authentication_activity_summary(events: list[Notification]) -> dict[str, int]:
    summary = {'total': len(events), 'success': 0, 'failed': 0, 'sign_out': 0, 'expired': 0, 'unknown': 0}
    for event in events:
        summary[authentication_event_kind(event)] += 1
    return summary


def account_mfa_factor(user_id: int) -> AuthenticationMfaFactor | None:
    """Read the current Account MFA presentation state below the HTTP layer."""
    return AuthenticationMfaFactor.query.filter_by(user_id=user_id).first()
