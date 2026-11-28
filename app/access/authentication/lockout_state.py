"""Transaction-scoped account lockout primitives; no HTTP or session admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.access.authentication.lockout_policy import (
    LockoutDecision,
    LockoutGate,
    LockoutMode,
    LockoutState,
    apply_outcome,
    inspect_state,
    utc,
)
from app.extensions.db import db
from app.models.authentication_security import AuthenticationAccountLockout, AuthenticationSecurityPolicy
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import system_actor_snapshot, unauthenticated_actor_snapshot
from app.platform_operations.notifications.event_catalog import event_category_key


@dataclass(frozen=True, slots=True)
class LockedAccountState:
    user_id: int
    revision: int
    record: AuthenticationAccountLockout | None
    decision: LockoutDecision
    observed_at: datetime


def _clock() -> datetime:
    # Use the database clock across instances; SQLite is only a local DML test
    # backend and does not qualify the row-lock/concurrency contract.
    if db.session.get_bind().dialect.name == 'sqlite':
        return datetime.now(UTC)
    return utc(db.session.execute(select(func.clock_timestamp())).scalar_one())


def lock_account_state(user_id: int) -> LockedAccountState | None:
    """Acquire account -> policy -> state locks in the caller's transaction.

    A missing/excluded account never creates durable failure state. Caller
    must verify a refreshed current local credential while this lock is held.
    """
    user = db.session.execute(
        select(User.id)
        .where(
            User.id == user_id,
            User.auth_source == 'database',
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
            User.is_super_admin.is_(False),
            User.password_hash != '',
        )
        .with_for_update(of=User)
    ).scalar_one_or_none()
    if user is None:
        return None
    policy = db.session.execute(
        select(AuthenticationSecurityPolicy.lockout_mode, AuthenticationSecurityPolicy.lockout_revision)
        .where(AuthenticationSecurityPolicy.id == 1)
        .with_for_update(read=True, of=AuthenticationSecurityPolicy)
    ).one_or_none()
    mode = LockoutMode(policy[0]) if policy is not None else LockoutMode.DISABLED
    revision = int(policy[1]) if policy is not None else 1
    if revision < 1:
        raise ValueError('Invalid account lockout policy revision.')
    record = None
    state = LockoutState()
    if mode != LockoutMode.DISABLED:
        record = db.session.execute(
            select(AuthenticationAccountLockout)
            .where(AuthenticationAccountLockout.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if record is not None and record.policy_revision > revision:
            raise ValueError('Account lockout state has a future policy revision.')
        if record is not None and record.policy_revision == revision:
            if not isinstance(record.failure_times, list) or any(
                not isinstance(item, str) for item in record.failure_times
            ):
                raise ValueError('Invalid committed failure window.')
            state = LockoutState(
                tuple(datetime.fromisoformat(item) for item in record.failure_times),
                record.cooldown_until,
                record.locked_until,
            )
    now = _clock()
    return LockedAccountState(user_id, revision, record, inspect_state(mode, state, now=now), now)


def _event(
    context: LockedAccountState,
    *,
    action: str,
    now: datetime,
    count: int,
    system: bool = False,
    password_valid: bool | None = None,
) -> Notification:
    actor = system_actor_snapshot() if system else unauthenticated_actor_snapshot()
    event = Notification()
    event.user_id = context.user_id
    event.event_type = 'authentication'
    event.category_key = event_category_key('authentication')
    event.actor_key = actor.key
    event.actor_label = actor.label
    event.actor_snapshot_json = actor.as_json()
    event.status = 'success' if system else 'info'
    event.title = action.replace('_', ' ').title()
    event.message = 'Local password protection observation recorded.'
    event.detail = 'Policy observation only; no authenticated session issuance is asserted.'
    event.metadata_json = {
        'audit_schema': 'authentication.security.v1',
        'access_action': action,
        'target_user_id': context.user_id,
        'policy_mode': context.decision.mode.value,
        'policy_revision': context.revision,
        'gate': context.decision.gate.value,
        'failure_count': count,
        'password_outcome': 'verified' if password_valid is True else 'invalid' if password_valid is False else None,
    }
    # Notify the resolved target once per actual enforced lock transition.
    # The same row is the committed Activity Audit; no second write or delivery.
    threshold = action == 'lockout_threshold_reached' and context.decision.mode == LockoutMode.ENFORCED
    if threshold:
        event.status = 'warning'
        event.title = 'Temporary Sign-in Lock'
        event.message = 'Repeated invalid credentials temporarily locked new local sign-ins.'
    event.deck_visible = threshold
    event.read_at = None if threshold else now
    event.created_at = now
    return event


def stage_password_outcome(context: LockedAccountState, *, password_valid: bool | None) -> LockoutState:
    """Stage once per locked attempt; caller must commit or roll back.

    No exception is swallowed. A rejected/failed audit commit must roll back
    the observation. No authenticated session, credential or lifecycle mutation.
    """
    decision = context.decision
    if decision.mode == LockoutMode.DISABLED:
        return LockoutState()
    now = _clock()
    if now < context.observed_at:
        raise ValueError('Account lockout clock moved backwards.')
    state = apply_outcome(decision, password_valid=password_valid, now=now)
    record = context.record
    if record is not None or state.failures:
        if record is None:
            record = AuthenticationAccountLockout(user_id=context.user_id)
            db.session.add(record)
        record.policy_revision = context.revision
        record.failure_times = [item.isoformat() for item in state.failures]
        record.cooldown_until = state.cooldown_until
        record.locked_until = state.locked_until
        record.updated_at = now
    if decision.auto_unlocked:
        db.session.add(_event(context, action='lockout_expired', now=now, count=0, system=True))
    if decision.gate != LockoutGate.OPEN:
        action = 'lockout_gate_rejected' if decision.blocked else 'lockout_gate_observed'
    elif password_valid is True:
        action = 'lockout_primary_reset'
    elif password_valid is False:
        action = 'lockout_failure'
        if state.locked_until is not None:
            action = 'lockout_threshold_reached'
        elif state.cooldown_until is not None:
            action = 'lockout_cooldown_started'
    else:
        return state
    db.session.add(
        _event(context, action=action, now=now, count=len(state.failures), password_valid=password_valid)
    )
    return state
