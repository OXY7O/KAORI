from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, or_, select

from sqlalchemy.orm import load_only

from app.access.authentication.mfa.policy import MfaGate, MfaPolicyMode, evaluate_mfa_policy
from app.access.authentication.session_lifecycle import SessionPolicy, read_session_policy
from app.extensions.db import db
from app.models import Notification, User
from app.models.authentication_security import AuthenticationMfaFactor, AuthenticationSecurityPolicy


def recent_authentication_events(user_id: int, *, limit: int = 5) -> list[Notification]:
    return (
        Notification.query.filter(
            Notification.user_id == user_id,
            or_(
                Notification.event_type == 'authentication',
                and_(
                    Notification.event_type == 'account_security',
                    Notification.metadata_json['security_action'].as_string() == 'password_change',
                ),
            ),
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(max(1, min(limit, 5)))
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
    return (
        AuthenticationMfaFactor.query.options(
            load_only(
                AuthenticationMfaFactor.enabled,
                AuthenticationMfaFactor.enrollment_expires_at,
                AuthenticationMfaFactor.enrollment_generation,
                AuthenticationMfaFactor.enrollment_authenticated,
                AuthenticationMfaFactor.replacement_generation,
                AuthenticationMfaFactor.replacement_expires_at,
                AuthenticationMfaFactor.recovery_hashes,
            )
        )
        .filter_by(user_id=user_id)
        .first()
    )


_PERSONAL_SECURITY_ACTIONS = {
    'mfa_enrollment_started': 'Authenticator Setup Started',
    'mfa_enrollment_confirmed': 'Authenticator Enrolled',
    'mfa_enrollment_cancelled': 'Authenticator Setup Cancelled',
    'mfa_replacement_started': 'Authenticator Replacement Started',
    'mfa_replacement_confirmed': 'Authenticator Replaced',
    'mfa_replacement_cancelled': 'Authenticator Replacement Cancelled',
    'mfa_recovery_regenerated': 'Recovery Codes Regenerated',
    'mfa_pending_material_cleanup': 'Pending Setup Removed',
    'mfa_challenge_verified': 'MFA Challenge Verified',
    'mfa_challenge_rejected': 'MFA Challenge Rejected',
    'lockout_threshold_reached': 'Login Protection Threshold',
    'lockout_admin_unlocked': 'Account Unlock Recorded',
    'lockout_expired': 'Temporary Lock Expired',
}


def personal_security_event_label(event: Notification) -> str | None:
    """Render only known personal actions; never echo arbitrary audit metadata."""
    metadata = event.metadata_json or {}
    if event.event_type == 'account_security' and metadata.get('security_action') == 'password_change':
        return 'Password Change Recorded'
    if event.event_type != 'authentication' or metadata.get('audit_schema') != 'authentication.security.v1':
        return None
    if metadata.get('target_user_id') != event.user_id or event.user_id is None:
        return None
    action = metadata.get('access_action')
    return _PERSONAL_SECURITY_ACTIONS.get(action) if isinstance(action, str) else None


@dataclass(frozen=True, slots=True)
class PersonalSecurityPosture:
    mfa_policy: str
    mfa_label: str
    mfa_tone: str
    mfa_detail: str
    idle_minutes: int
    absolute_hours: int
    remember_label: str
    remember_detail: str


def build_personal_security_posture(
    *, mode: str, enrolled: bool, privileged: bool, session_policy: SessionPolicy,
) -> PersonalSecurityPosture:
    """Read-only effective next-sign-in policy; not proof of current-session MFA."""
    decision = evaluate_mfa_policy(mode, privileged=privileged, enrolled=enrolled)
    if decision.mode == MfaPolicyMode.DISABLED:
        label, tone, detail = 'Disabled by Policy', 'unknown', 'A stored factor does not require a sign-in challenge.'
    elif decision.gate == MfaGate.ENROLLMENT_REQUIRED:
        label, tone, detail = 'Enrollment Required', 'warning', 'Complete authenticator enrollment at required sign-in.'
    elif decision.gate == MfaGate.CHALLENGE:
        label, tone, detail = 'Challenge Required', 'normal', 'A verified factor is required at the next applicable sign-in.'
    else:
        label, tone, detail = 'Not Enrolled', 'unknown', 'Current policy does not require this account to enroll.'
    idle, absolute = session_policy.limits(privileged=privileged)
    if privileged:
        remember_label, remember_detail = 'Not Permitted', 'Privileged accounts cannot use persistent sign-in.'
    elif not session_policy.regular_remember:
        remember_label, remember_detail = 'Disabled by Policy', 'Persistent sign-in is disabled for ordinary accounts.'
    else:
        remember_label, remember_detail = 'Permitted by Policy', 'Where offered, sign-in remains bounded by session deadlines.'
    return PersonalSecurityPosture(
        mfa_policy=decision.mode.value,
        mfa_label=label,
        mfa_tone=tone,
        mfa_detail=detail,
        idle_minutes=int(idle.total_seconds() // 60),
        absolute_hours=int(absolute.total_seconds() // 3600),
        remember_label=remember_label,
        remember_detail=remember_detail,
    )


def read_personal_security_posture(user: User) -> PersonalSecurityPosture:
    """Project exact current account and policy without loading factor/secret material."""
    mode = db.session.execute(
        select(AuthenticationSecurityPolicy.mfa_mode).where(AuthenticationSecurityPolicy.id == 1)
    ).scalar_one_or_none()
    enrolled = db.session.execute(
        select(AuthenticationMfaFactor.enabled).where(AuthenticationMfaFactor.user_id == user.id)
    ).scalar_one_or_none()
    return build_personal_security_posture(
        mode=mode if mode is not None else 'disabled',
        enrolled=enrolled is True,
        privileged=bool(user.is_admin_level),
        session_policy=read_session_policy(),
    )
