"""Narrow management-plane recovery of KAORI-owned Bot Protection (#4014).

The caller must additionally restrict shell/container access and obtain incident
authorization. This is not a browser login or a replacement identity authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from re import fullmatch
from uuid import uuid4

from flask import current_app, has_request_context
from sqlalchemy import select, update

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.bot_protection.service import BotPolicyMode
from app.access.authentication.lockout_governance import GovernanceEvidence
from app.access.authentication.lockout_policy import LockoutMode
from app.access.authentication.mfa.service import require_personal_factor_assurance, stage_admin_totp_assurance
from app.extensions.db import db
from app.models.authentication_security import AuthenticationSecurityPolicy
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import actor_snapshot_for_user
from app.platform_operations.notifications.event_catalog import event_category_key
from app.platform_operations.notifications.metadata import redact_operational_metadata


class BreakGlassDenied(ValueError):
    """Unqualified management recovery request."""


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    previous_mode: str
    new_mode: str
    correlation: str


@dataclass(frozen=True, slots=True)
class LoginProtectionRecoveryResult(RecoveryResult):
    previous_revision: int
    new_revision: int


def _stage_event(
    actor: User, *, operator: str, evidence: GovernanceEvidence, result: RecoveryResult
) -> None:
    snapshot = actor_snapshot_for_user(actor)
    event = Notification()
    event.user_id = actor.id
    event.event_type = 'authentication'
    event.category_key = event_category_key('authentication')
    event.actor_key = snapshot.key
    event.actor_label = snapshot.label
    event.actor_snapshot_json = snapshot.as_json()
    changed = result.previous_mode != result.new_mode
    login_recovery = isinstance(result, LoginProtectionRecoveryResult)
    control = 'Login Protection' if login_recovery else 'Bot Protection'
    event.status = 'warning' if changed else 'info'
    event.title = f'Break-Glass {control} Recovery'
    event.message = f'{control} disabled by an authorized recovery principal.' if changed else (
        f'{control} was already disabled; no policy transition occurred.'
    )
    event.detail = 'Management CLI only; no browser session, credential reset or MFA bypass was issued.'
    event.metadata_json = redact_operational_metadata({
        'audit_schema': 'authentication.security.v1',
        'access_action': 'lockout_break_glass_recovery' if login_recovery else 'bot_break_glass_recovery',
        'actor_id': actor.id,
        'target_user_id': actor.id,
        'trigger_type': 'cli',
        'operator_reference': operator,
        'operator_reference_verified': False,
        'ticket': evidence.ticket,
        'reason': evidence.reason,
        'assurance': 'local_current_password_and_totp',
        'previous_policy_mode': result.previous_mode,
        'new_policy_mode': result.new_mode,
        'result': 'changed' if changed else 'unchanged',
        'correlation_id': result.correlation,
        **({'previous_revision': result.previous_revision, 'new_revision': result.new_revision}
           if isinstance(result, LoginProtectionRecoveryResult) else {}),
    })
    event.deck_visible = True
    event.created_at = datetime.now(UTC)
    db.session.add(event)


def _authorize_recovery(
    *, username: str, operator: str, ticket: str, reason: str, acknowledged: bool,
) -> tuple[User, str, GovernanceEvidence]:
    """Reuse one management authorization and lock the actual local principal."""
    if has_request_context() or not current_app.config.get('AUTH_BREAK_GLASS_RECOVERY_ALLOWED'):
        raise BreakGlassDenied('Recovery must be explicitly authorized in an isolated CLI process.')
    if acknowledged is not True:
        raise BreakGlassDenied('Explicit acknowledgement is required.')
    username = username.strip()
    operator = operator.strip()
    if not 1 <= len(username) <= 100 or not fullmatch(r'[A-Za-z0-9][A-Za-z0-9._@/-]{2,79}', operator):
        raise BreakGlassDenied('Valid recovery principal and operator reference required.')
    evidence = GovernanceEvidence.parse(ticket, reason)
    actor = db.session.execute(
        select(User).where(
            User.username == username, User.auth_source == 'database',
            User.is_super_admin.is_(True), User.account_is_active.is_(True),
            User.deleted_at.is_(None),
        ).with_for_update(of=User).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        actor is None
        or actor.auth_source != 'database'
        or not actor.is_super_admin
        or session_admission_reason(actor, source='database') is not None
    ):
        raise BreakGlassDenied('Recovery assurance rejected.')
    return actor, operator, evidence


def recover_bot_protection(
    *, username: str, operator: str, ticket: str, reason: str,
    password: str, code: str, acknowledged: bool,
) -> RecoveryResult:
    """Commit one narrow operation, never authenticate a browser session.

    Operator reference is declared, not OS identity proof. Correlate with
    independent management access/dual-control logs. No network dependency
    on CAPTCHA, external IdP or Redis is introduced into this transaction.
    """
    try:
        actor, operator, evidence = _authorize_recovery(
            username=username, operator=operator, ticket=ticket, reason=reason, acknowledged=acknowledged,
        )
        # Lock account -> policy -> factor. Select only required policy fields,
        # so an unavailable encrypted Turnstile secret cannot obstruct recovery.
        policy = AuthenticationSecurityPolicy
        previous = db.session.execute(
            select(policy.bot_mode).where(policy.id == 1).with_for_update(of=policy)
        ).scalar_one_or_none()
        if previous is None:
            raise BreakGlassDenied('Authentication policy initialization required.')
        mode = BotPolicyMode(previous)
        require_personal_factor_assurance(actor, password, now=datetime.now(UTC), strict_primary=True)
        stage_admin_totp_assurance(actor, code)
        result = RecoveryResult(mode.value, BotPolicyMode.DISABLED.value, uuid4().hex)
        if mode == BotPolicyMode.ALWAYS:
            db.session.execute(update(policy).where(policy.id == 1).values(
                bot_mode=BotPolicyMode.DISABLED.value, bot_tested_at=None, updated_at=datetime.now(UTC)
            ))
        _stage_event(actor, operator=operator, evidence=evidence, result=result)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def recover_login_protection(
    *, username: str, operator: str, ticket: str, reason: str,
    password: str, code: str, acknowledged: bool, expected_revision: int,
) -> LoginProtectionRecoveryResult:
    """Rollback only the optional committed policy, without Redis or HTTP admission.

    The independent per-IP limiter is not modified. This cannot recover a
    failed Redis service or issue a login session. Old account observations
    remain stored and are fenced by the incremented policy revision.
    """
    try:
        actor, operator, evidence = _authorize_recovery(
            username=username, operator=operator, ticket=ticket, reason=reason, acknowledged=acknowledged,
        )
        policy = AuthenticationSecurityPolicy
        row = db.session.execute(
            select(policy.lockout_mode, policy.lockout_revision)
            .where(policy.id == 1).with_for_update(of=policy)
        ).one_or_none()
        if row is None:
            raise BreakGlassDenied('Authentication policy initialization required.')
        mode, revision = LockoutMode(row[0]), int(row[1])
        if type(expected_revision) is not int or revision < 1 or expected_revision != revision:
            raise BreakGlassDenied('Policy revision changed; inspect committed state before retrying.')
        require_personal_factor_assurance(actor, password, now=datetime.now(UTC), strict_primary=True)
        stage_admin_totp_assurance(actor, code)
        changed = mode != LockoutMode.DISABLED
        result = LoginProtectionRecoveryResult(
            mode.value, LockoutMode.DISABLED.value, uuid4().hex, revision, revision + int(changed),
        )
        if changed:
            db.session.execute(
                update(policy).where(policy.id == 1).values(
                    lockout_mode=LockoutMode.DISABLED.value,
                    lockout_revision=result.new_revision,
                    updated_at=datetime.now(UTC),
                )
            )
        _stage_event(actor, operator=operator, evidence=evidence, result=result)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise
