"""Secret-free committed evidence for MFA and authentication policy mutations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from flask import request, session

from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import actor_snapshot_for_user, unauthenticated_actor_snapshot
from app.platform_operations.notifications.event_catalog import event_category_key

MfaSecurityAction = Literal[
    'mfa_enrollment_started',
    'mfa_enrollment_confirmed',
    'mfa_challenge_verified',
    'mfa_challenge_rejected',
    'mfa_recovery_regenerated',
    'mfa_disabled',
    'mfa_policy_changed',
    'bot_policy_changed',
]


def stage_authentication_security_event(
    user: User,
    *,
    action: MfaSecurityAction,
    authenticated: bool,
    success: bool,
    previous_mode: str | None = None,
    next_mode: str | None = None,
) -> Notification:
    """Return an audit-only event; caller owns the transaction and commit.

    The event includes no OTP, recovery code, encrypted seed, CAPTCHA token or
    provider secret. Primary-only pending login never claims a verified actor.
    """
    actor = actor_snapshot_for_user(user) if authenticated else unauthenticated_actor_snapshot()
    now = datetime.now(UTC)
    return Notification(
        user_id=user.id,
        event_type='authentication',
        category_key=event_category_key('authentication'),
        actor_key=actor.key,
        actor_label=actor.label,
        actor_snapshot_json=actor.as_json(),
        status='success' if success else 'warning',
        title=action.replace('_', ' ').title(),
        message='Authentication security control state recorded.',
        detail='KAORI committed a security control transition without factor or credential values.',
        metadata_json={
            'audit_schema': 'authentication.security.v1',
            'access_action': action,
            'result': 'success' if success else 'rejected',
            'target_user_id': user.id,
            'previous_policy_mode': previous_mode,
            'new_policy_mode': next_mode,
            'request_method': request.method,
            'request_path': request.path[:200],
            'session_reference': session.get('auth_session_ref') if authenticated else None,
        },
        deck_visible=False,
        read_at=now,
        created_at=now,
    )
