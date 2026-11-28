"""Governed lockout mutations and read-only account projection (#5326)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from re import fullmatch

from flask import current_app
from sqlalchemy import select, update

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.lockout_policy import LockoutGate, LockoutMode, utc
from app.access.authentication.lockout_state import lock_account_state
from app.access.authentication.login_protection import probe_shared_login_protection, read_login_policy
from app.access.authentication.mfa.service import require_personal_factor_assurance, stage_admin_totp_assurance
from app.access.authentication.session_lifecycle import SessionDeadlines, read_session_policy, session_deadlines
from app.extensions.db import db
from app.models.authentication_security import (
    AuthenticationAccountLockout,
    AuthenticationMfaFactor,
    AuthenticationSecurityPolicy,
)
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import actor_snapshot_for_user
from app.platform_operations.notifications.event_catalog import event_category_key
from app.platform_operations.notifications.metadata import redact_operational_metadata, redact_operational_text


class LockoutGovernanceDenied(ValueError):
    """Invalid authorization, assurance, input, or stale mutation."""


@dataclass(frozen=True, slots=True)
class GovernanceEvidence:
    ticket: str
    reason: str

    @classmethod
    def parse(cls, ticket: str, reason: str) -> GovernanceEvidence:
        ticket, reason = ticket.strip(), reason.strip()
        if not fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{2,79}', ticket) or not 10 <= len(reason) <= 300:
            raise LockoutGovernanceDenied('A bounded incident/change reference and reason are required.')
        safe = redact_operational_text(reason, limit=300)
        if safe != reason or not safe:
            raise LockoutGovernanceDenied('Use a non-sensitive single-line reason.')
        return cls(ticket, safe)


def can_view_lockout(actor: User, target: User) -> bool:
    return bool(
        actor.has_permission('users.view')
        and actor.has_permission('users.reset_password')
        and (not target.is_admin_level or actor.is_super_admin)
    )


def can_unlock_account(actor: User, target: User) -> bool:
    return bool(
        can_view_lockout(actor, target)
        and actor.auth_source == 'database'
        and actor.id != target.id
        and target.auth_source == 'database'
        and target.is_active
        and not target.is_super_admin
    )


def _lock_users(actor_id: int, target_id: int | None = None) -> dict[int, User]:
    ids = sorted({actor_id} if target_id is None else {actor_id, target_id})
    rows = db.session.execute(
        select(User).where(User.id.in_(ids)).order_by(User.id)
        .with_for_update(of=User).execution_options(populate_existing=True)
    ).scalars().all()
    return {user.id: user for user in rows}


def _validate_actor(actor: User | None, *, generation: int, permission: str) -> User:
    if (
        actor is None
        or actor.auth_source != 'database'
        or actor.auth_session_version != generation
        or session_admission_reason(actor, source='database') is not None
        or not actor.has_permission(permission)
        or not isinstance(session_deadlines(actor, read_session_policy(), datetime.now(UTC)), SessionDeadlines)
    ):
        raise LockoutGovernanceDenied('Current local administrator assurance is required.')
    return actor


def _step_up(actor: User, password: str, code: str) -> None:
    require_personal_factor_assurance(actor, password, now=datetime.now(UTC), strict_primary=True)
    stage_admin_totp_assurance(actor, code)


def _event(
    actor: User,
    *,
    target_id: int | None,
    action: str,
    evidence: GovernanceEvidence,
    metadata: dict[str, str | int],
    changed: bool,
) -> Notification:
    snapshot = actor_snapshot_for_user(actor)
    now = datetime.now(UTC)
    event = Notification()
    event.user_id = target_id if target_id is not None else actor.id
    event.event_type = 'authentication'
    event.category_key = event_category_key('authentication')
    event.actor_key = snapshot.key
    event.actor_label = snapshot.label
    event.actor_snapshot_json = snapshot.as_json()
    event.status = 'success' if changed else 'info'
    event.title = action.replace('_', ' ').title()
    event.message = 'Governed login protection change recorded.' if changed else 'Login protection was unchanged.'
    event.detail = 'No password, MFA factor, lifecycle status or session generation was changed.'
    event.metadata_json = redact_operational_metadata({
        'audit_schema': 'authentication.security.v1',
        'access_action': action,
        'actor_id': actor.id,
        'target_user_id': target_id,
        'ticket': evidence.ticket,
        'reason': evidence.reason,
        'assurance': 'local_current_password_and_totp',
        **metadata,
    })
    event.deck_visible = changed
    event.read_at = None if changed else now
    event.created_at = now
    return event


def validate_activation(previous: LockoutMode, requested: LockoutMode) -> None:
    if requested == previous or requested == LockoutMode.DISABLED:
        return
    if not current_app.config.get('AUTH_LOCKOUT_MONITOR_ALLOWED'):
        raise LockoutGovernanceDenied('Login protection activation is on hold.')
    if requested == LockoutMode.ENFORCED and (
        previous != LockoutMode.MONITOR_ONLY or not current_app.config.get('AUTH_LOCKOUT_ENFORCEMENT_ALLOWED')
    ):
        raise LockoutGovernanceDenied('Enforcement requires separately qualified Monitor Only operation.')
    probe_shared_login_protection()
    # The operator flags attest external qualification, not something proved by this query.
    enrolled_recovery = db.session.execute(
        select(User.id).join(AuthenticationMfaFactor, AuthenticationMfaFactor.user_id == User.id)
        .where(
            User.auth_source == 'database', User.is_super_admin.is_(True),
            User.account_is_active.is_(True), User.deleted_at.is_(None),
            User.password_hash != '', AuthenticationMfaFactor.enabled.is_(True),
        ).limit(1)
    ).scalar_one_or_none()
    if enrolled_recovery is None:
        raise LockoutGovernanceDenied('An enrolled local recovery administrator is required.')


def stage_policy_change(
    *,
    actor_id: int,
    generation: int,
    requested: LockoutMode,
    expected_revision: int,
    evidence: GovernanceEvidence,
    password: str,
    code: str,
) -> bool:
    """Stage policy, fresh proof and evidence; caller commits or rolls back."""
    actor = _validate_actor(_lock_users(actor_id).get(actor_id), generation=generation,
                            permission='identity_providers.manage')
    policy = AuthenticationSecurityPolicy
    row = db.session.execute(
        select(policy.lockout_mode, policy.lockout_revision)
        .where(policy.id == 1).with_for_update(of=policy)
    ).one_or_none()
    if row is None:
        raise LockoutGovernanceDenied('Authentication policy initialization is required.')
    previous, revision = LockoutMode(row[0]), int(row[1])
    if revision < 1 or revision != expected_revision:
        raise LockoutGovernanceDenied('Policy revision changed; refresh and try again.')
    validate_activation(previous, requested)
    _step_up(actor, password, code)
    changed = requested != previous
    next_revision = revision + int(changed)
    if changed:
        db.session.execute(update(policy).where(policy.id == 1).values(
            lockout_mode=requested.value, lockout_revision=next_revision, updated_at=datetime.now(UTC)
        ))
    db.session.add(_event(
        actor, target_id=None, action='lockout_policy_changed' if changed else 'lockout_policy_unchanged',
        evidence=evidence, changed=changed, metadata={
            'previous_mode': previous.value, 'new_mode': requested.value,
            'previous_revision': revision, 'new_revision': next_revision,
        },
    ))
    return changed


def stage_manual_unlock(
    *,
    actor_id: int,
    generation: int,
    target_id: int,
    expected_revision: int,
    expected_deadline: str,
    evidence: GovernanceEvidence,
    password: str,
    code: str,
) -> None:
    """Clear only the exact active committed lock, never account lifecycle."""
    accounts = _lock_users(actor_id, target_id)
    actor = _validate_actor(accounts.get(actor_id), generation=generation, permission='users.reset_password')
    target = accounts.get(target_id)
    if target is None or not can_unlock_account(actor, target):
        raise LockoutGovernanceDenied('This account cannot be unlocked by this administrator.')
    context = lock_account_state(target_id)
    if (
        context is None or context.record is None or context.revision != expected_revision
        or context.decision.mode != LockoutMode.ENFORCED or context.decision.gate != LockoutGate.LOCKED
        or context.decision.state.locked_until is None
        or context.decision.state.locked_until.isoformat() != expected_deadline
    ):
        raise LockoutGovernanceDenied('The committed lock changed; refresh and try again.')
    _step_up(actor, password, code)
    record = context.record
    record.failure_times = []
    record.cooldown_until = None
    record.locked_until = None
    record.updated_at = datetime.now(UTC)
    db.session.add(_event(
        actor, target_id=target_id, action='lockout_admin_unlocked', evidence=evidence, changed=True,
        metadata={'policy_revision': context.revision, 'previous_locked_until': expected_deadline},
    ))


def lockout_views(actor: User | None, users: list[User]) -> dict[int, dict[str, object]]:
    """Page-bounded read projection; no failure timestamps or credential material."""
    if actor is None:
        return {}
    visible = [user for user in users if can_view_lockout(actor, user)]
    if not visible:
        return {}
    mode, revision = read_login_policy()
    model = AuthenticationAccountLockout
    rows = db.session.execute(
        select(model.user_id, model.cooldown_until, model.locked_until)
        .where(model.user_id.in_([user.id for user in visible]), model.policy_revision == revision)
    ).all() if mode != LockoutMode.DISABLED else []
    deadlines = {row[0]: (row[1], row[2]) for row in rows}
    now = datetime.now(UTC)
    result: dict[int, dict[str, object]] = {}
    for user in visible:
        state, deadline = 'Open', None
        if user.auth_source != 'database':
            state = 'Provider Managed'
        elif user.is_super_admin:
            state = 'Recovery Protected'
        elif not user.is_active:
            state = 'Not Applicable'
        elif mode == LockoutMode.DISABLED:
            state = 'Disabled'
        else:
            cooldown, locked = deadlines.get(user.id, (None, None))
            if locked is not None and utc(locked) > now:
                deadline = utc(locked)
                state = 'Locked' if mode == LockoutMode.ENFORCED else 'Would Lock'
            elif cooldown is not None and utc(cooldown) > now:
                deadline = utc(cooldown)
                state = 'Cooldown' if mode == LockoutMode.ENFORCED else 'Would Throttle'
        result[user.id] = {
            'label': state, 'deadline': deadline, 'revision': revision,
            'deadline_token': deadline.isoformat() if deadline is not None else '',
            'can_unlock': state == 'Locked' and can_unlock_account(actor, user),
        }
    return result
