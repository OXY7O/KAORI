"""Controlled out-of-band recovery for authentication challenge outages.

These privileged CLI actions require operator shell access, an explicit incident
reference, and confirmation; they are not exposed to any HTTP or UI route.
"""

from __future__ import annotations

import getpass
from datetime import UTC, datetime

import click
from flask.cli import with_appcontext
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.authentication_security import AuthenticationMfaFactor, AuthenticationSecurityPolicy
from app.models.notification import Notification
from app.models.user import User
from app.platform_operations.notifications.actors import system_actor_snapshot
from app.platform_operations.notifications.event_catalog import event_category_key
from app.platform_operations.notifications.metadata import redact_operational_text


def _recovery_event(action: str, reason: str, *, user_id: int | None = None) -> Notification:
    actor = system_actor_snapshot()
    now = datetime.now(UTC)
    return Notification(
        user_id=user_id,
        event_type='authentication',
        category_key=event_category_key('authentication'),
        actor_key=actor.key,
        actor_label=actor.label,
        actor_snapshot_json=actor.as_json(),
        title='Authentication Recovery Control',
        status='warning',
        message='An authenticated shell operator invoked governed security recovery.',
        detail='Inspect the recorded operational incident and CLI execution evidence.',
        metadata_json={
            'audit_schema': 'authentication.security.recovery.v1',
            'action': action,
            'recovery_reason': redact_operational_text(reason, limit=160),
            'shell_operator': getpass.getuser()[:80],
            'target_user_id': user_id,
        },
        deck_visible=False,
        read_at=now,
        created_at=now,
    )


@click.command('disable-bot-protection')
@click.option('--reason', required=True, help='Approved incident/change reference; no secrets.')
@click.option('--yes', is_flag=True, help='Explicitly acknowledge the emergency security policy reduction.')
@with_appcontext
def disable_bot_protection(reason: str, yes: bool) -> None:
    """Disable a failing challenge without relying on an authenticated browser."""
    if not reason.strip() or len(reason.strip()) > 160:
        raise click.ClickException('An approved bounded incident/change reference is required.')
    if not yes:
        click.confirm('Disable live Bot Protection? This reduces login assurance.', abort=True)
    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        if policy is None or policy.bot_mode == 'disabled':
            raise click.ClickException('Bot Protection is already disabled.')
        policy.bot_mode = 'disabled'
        db.session.add(_recovery_event('bot_policy_emergency_disabled', reason))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise click.ClickException('Recovery database operation failed; no change committed.') from exc
    click.echo('Bot Protection disabled; audit event committed. Verify sign-in and file incident evidence.')


@click.command('reset-user-mfa')
@click.option('--username', required=True, help='Existing account username for controlled recovery.')
@click.option('--reason', required=True, help='Approved incident/change reference; no secrets.')
@click.option('--yes', is_flag=True, help='Explicitly acknowledge the factor reset and session revocation.')
@with_appcontext
def reset_user_mfa(username: str, reason: str, yes: bool) -> None:
    """Delete a lost factor, forcing re-enrollment under mandatory policy."""
    if not reason.strip() or len(reason.strip()) > 160:
        raise click.ClickException('An approved bounded incident/change reference is required.')
    if not yes:
        click.confirm('Reset MFA and revoke all sessions for this account?', abort=True)
    try:
        user = User.query.filter_by(username=username, deleted_at=None).with_for_update().first()
        if user is None:
            raise click.ClickException('Target user was not found.')
        factor = AuthenticationMfaFactor.query.filter_by(user_id=user.id).with_for_update().first()
        if factor is None:
            raise click.ClickException('Target account has no MFA factor.')
        db.session.delete(factor)
        db.session.execute(
            update(User)
            .where(User.id == user.id)
            .values(auth_session_version=func.coalesce(User.auth_session_version, 1) + 1)
        )
        db.session.add(_recovery_event('mfa_factor_recovery_reset', reason, user_id=user.id))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise click.ClickException('MFA recovery failed; no change committed.') from exc
    click.echo('MFA factor reset; all account sessions revoked. Audit event committed.')
