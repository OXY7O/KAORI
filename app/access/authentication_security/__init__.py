"""Access-owned Authentication Security policy and provider management."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import cast

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_fresh, logout_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.authentication.bot_protection.registry import bot_provider_definitions
from app.access.authentication.bot_protection.service import TEST_SECRET_KEYS, TEST_SITE_KEYS, BotPolicyMode
from app.access.authentication.bot_protection.turnstile import (
    TurnstileVerificationConfig,
    _configuration_ready,
    verify_turnstile,
)
from app.access.authentication.lockout_governance import GovernanceEvidence, stage_policy_change
from app.access.authentication.lockout_policy import LockoutMode
from app.access.authentication.login_protection import LoginProtectionUnavailable
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaPolicyMode
from app.access.authentication.mfa.service import mfa_enrolled, mfa_policy_mode
from app.access.authentication.session import clear_authenticated_session, parse_authenticated_user_identifier
from app.access.authentication.session_lifecycle import SessionPolicy
from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.extensions.limiter import limiter
from app.models import User
from app.models.authentication_security import AuthenticationSecurityPolicy
from app.platform_operations.notifications.feedback import (
    OperationalDeliveryPolicy,
    OperationalFeedbackSpec,
    build_operational_feedback,
    queue_operational_feedback,
)
from app.platform_operations.notifications.service import queue_transient_feedback
from app.security.credentials import CredentialEncryptionError

bp = Blueprint('authentication_security', __name__)

_TABS = (
    ('overview', 'Overview', 'layout-dashboard'),
    ('mfa', 'Multi-Factor Authentication', 'shield-check'),
    ('bot', 'Bot Protection', 'bot'),
    ('sessions', 'Session Security', 'monitor-check'),
)


def active_security_tab(requested: str | None) -> str:
    supported = {key for key, _, _ in _TABS}
    return requested if requested in supported else 'overview'


@bp.get('/')
@permission_required('identity_providers.view')
def index():
    active_tab = active_security_tab(request.args.get('tab'))
    tabs = tuple(
        (key, label, icon, url_for('access.authentication_security.index', tab=key)) for key, label, icon in _TABS
    )
    submenu_tabs = tuple((key, label, icon, None, href) for key, label, icon, href in tabs)
    row = db.session.get(AuthenticationSecurityPolicy, 1)
    context = {
        'lockout_mode': row.lockout_mode if row is not None else 'disabled',
        'lockout_revision': row.lockout_revision if row is not None else 1,
        'lockout_initialized': row is not None,
        'lockout_monitor_allowed': bool(current_app.config.get('AUTH_LOCKOUT_MONITOR_ALLOWED')),
        'lockout_enforcement_allowed': bool(current_app.config.get('AUTH_LOCKOUT_ENFORCEMENT_ALLOWED')),
        'can_manage_lockout': bool(
            current_user.has_permission('identity_providers.manage') and current_user.auth_source == 'database'
        ),
        'bot_mode': row.bot_mode if row is not None else 'disabled',
        'bot_provider_key': row.bot_provider_key if row is not None else 'cloudflare_turnstile',
        'bot_site_key': row.bot_site_key if row is not None else '',
        'bot_hostname': row.bot_hostname if row is not None else '',
        'bot_has_secret': bool(row is not None and row.bot_secret_key),
        'bot_tested_at': row.bot_tested_at if row is not None else None,
        'active_tab': active_tab,
        'tabs': tabs,
        'submenu_tabs': submenu_tabs,
        'mfa_modes': tuple(mode.value for mode in MfaPolicyMode),
        'mfa_policy_mode': mfa_policy_mode(),
        'session_policy': SessionPolicy.from_record(row),
        'can_manage_authentication_security': current_user.has_permission('identity_providers.manage'),
        'bot_providers': bot_provider_definitions(),
    }
    if (
        request.headers.get('HX-Request') == 'true'
        and request.headers.get('HX-Target') == 'authentication-security-page'
    ):
        return render_template('access/authentication_security/partials/_page_content.html', **context)
    return render_template('access/authentication_security/index.html', **context)


def queue_committed_mfa_policy_feedback(*, status: str, title: str, message: str) -> None:
    """Present already-committed policy audit without creating a second record."""
    queue_operational_feedback(
        build_operational_feedback(
            OperationalFeedbackSpec(
                status=status,
                title=title,
                message=message,
                activity_audit_saved=True,
                notification_deck_visible=False,
                delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
            )
        )
    )


@bp.post('/session/policy')
@permission_required('identity_providers.manage')
def save_session_policy():
    """Persist policy and invalidate generations atomically; no-op is audit-only."""
    try:
        validate_csrf(request.form.get('csrf_token'))
        remember = request.form.get('session_regular_remember')
        if remember not in ('enabled', 'disabled'):
            raise ValueError('Invalid Remember Me policy.')
        requested = SessionPolicy(
            privileged_idle_minutes=int(request.form.get('session_privileged_idle_minutes', '')),
            privileged_absolute_hours=int(request.form.get('session_privileged_absolute_hours', '')),
            regular_idle_minutes=int(request.form.get('session_regular_idle_minutes', '')),
            regular_absolute_hours=int(request.form.get('session_regular_absolute_hours', '')),
            warning_minutes=int(request.form.get('session_warning_minutes', '')),
            regular_remember=remember == 'enabled',
        )
    except (ValidationError, TypeError, ValueError):
        abort(400)
    if request.form.get('acknowledge_session_policy_impact') != 'yes':
        abort(400)

    actor = cast(User, current_user._get_current_object())
    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        previous = SessionPolicy.from_record(policy)
        changed = previous != requested
        if changed:
            if policy is None:
                policy = AuthenticationSecurityPolicy(id=1)
                db.session.add(policy)
            policy.session_privileged_idle_minutes = requested.privileged_idle_minutes
            policy.session_privileged_absolute_hours = requested.privileged_absolute_hours
            policy.session_regular_idle_minutes = requested.regular_idle_minutes
            policy.session_regular_absolute_hours = requested.regular_absolute_hours
            policy.session_warning_minutes = requested.warning_minutes
            policy.session_regular_remember = requested.regular_remember
            # Revoke all existing human generations, including inactive users.
            # A subsequent enablement must not resurrect a cookie governed by
            # a previous policy. Worker identities are not User sessions.
            db.session.execute(
                update(User).values(
                    auth_session_version=func.coalesce(User.auth_session_version, 1) + 1,
                    auth_session_issued_at=None,
                    auth_session_activity_at=None,
                    updated_at=User.updated_at,
                )
            )
        db.session.add(
            stage_authentication_security_event(
                actor,
                action='session_policy_changed' if changed else 'session_policy_unchanged',
                authenticated=True,
                success=True,
                previous_policy=asdict(previous),
                next_policy=asdict(requested),
            )
        )
        db.session.commit()
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        current_app.logger.warning('Session policy change was not committed.', exc_info=True)
        queue_transient_feedback(
            status='error',
            title='Session policy not saved',
            message='The policy could not be committed; no session changes were applied.',
        )
        abort(503)

    if changed:
        logout_user()
        clear_authenticated_session()
        queue_committed_mfa_policy_feedback(
            status='success',
            title='Session policy updated',
            message='Session policy saved and existing sessions revoked; sign in again to continue.',
        )
        return redirect(url_for('auth.login'))
    queue_committed_mfa_policy_feedback(
        status='info',
        title='Session policy unchanged',
        message='The selected session policy is already active; no sessions were revoked.',
    )
    return redirect(url_for('access.authentication_security.index', tab='sessions'))


@bp.post('/mfa/policy')
@permission_required('identity_providers.manage')
def save_mfa_policy():
    """Commit policy and audit together; make session-revocation feedback visible."""
    try:
        validate_csrf(request.form.get('csrf_token'))
        requested = MfaPolicyMode(str(request.form.get('mfa_mode') or ''))
    except (ValidationError, ValueError):
        abort(400)
    if request.form.get('acknowledge_policy_impact') != 'yes':
        abort(400)

    actor = cast(User, current_user._get_current_object())
    if requested in (MfaPolicyMode.REQUIRED_PRIVILEGED, MfaPolicyMode.REQUIRED_ALL):
        # A mandatory policy cannot strand the final local recovery authority.
        recovery_admins = User.query.filter_by(
            is_super_admin=True, auth_source='database', account_is_active=True, deleted_at=None
        ).all()
        if not any(mfa_enrolled(item.id) for item in recovery_admins):
            abort(409, description='Enroll an active Local Database Super Admin before requiring MFA.')

    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        if policy is None:
            policy = AuthenticationSecurityPolicy()
            policy.id = 1
            policy.mfa_mode = 'disabled'
            db.session.add(policy)
        previous = policy.mfa_mode
        changed = previous != requested.value
        if changed:
            policy.mfa_mode = requested.value
            # Revocation and audit must commit as ONE transaction, never
            # allow a success toast if either DB mutation fails.
            db.session.execute(
                update(User)
                .where(User.account_is_active.is_(True), User.deleted_at.is_(None))
                .values(auth_session_version=func.coalesce(User.auth_session_version, 1) + 1)
            )
        db.session.add(
            stage_authentication_security_event(
                actor,
                action='mfa_policy_changed' if changed else 'mfa_policy_unchanged',
                authenticated=True,
                success=True,
                previous_mode=previous,
                next_mode=requested.value,
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning('MFA policy change was not committed.', exc_info=True)
        queue_transient_feedback(
            status='error',
            title='MFA policy not saved',
            message='The security policy could not be committed; no session changes were applied.',
        )
        abort(503)

    if changed:
        # The committed generation update also invalidated THIS administrator.
        # Explicitly clear the old login BEFORE queuing the result; otherwise
        # the next request's user loader can discard the toast along with the
        # now-invalid session cookie.
        logout_user()
        clear_authenticated_session()
        queue_committed_mfa_policy_feedback(
            status='success',
            title='MFA policy updated',
            message='MFA policy saved and existing sessions revoked; sign in again to continue.',
        )
        return redirect(url_for('auth.login'))

    # An unchanged selection is an audited user action, not a policy transition.
    # Do not revoke sessions or claim the configuration changed.
    queue_committed_mfa_policy_feedback(
        status='info',
        title='MFA policy unchanged',
        message='The selected MFA policy is already active; no sessions were revoked.',
    )
    return redirect(url_for('access.authentication_security.index', tab='mfa'))


def _validate_bot_credential_fields(site_key: str, hostname: str, submitted_secret: str) -> None:
    """Preserve bounded, non-whitespace credential validation before policy writes."""
    if len(site_key) > 255 or len(hostname) > 253 or len(submitted_secret) > 256:
        abort(400)
    if submitted_secret and any(char.isspace() for char in submitted_secret):
        abort(400)


def _bot_configuration_qualified(site_key: str, hostname: str, effective_secret: str) -> bool:
    candidate = TurnstileVerificationConfig(
        secret_key=effective_secret, expected_hostname=hostname, expected_action='login'
    )
    return bool(
        site_key
        and site_key.isascii()
        and not any(char.isspace() for char in site_key)
        and _configuration_ready(candidate)
    )


def _bot_configuration_changed(
    policy: AuthenticationSecurityPolicy, site_key: str, hostname: str, submitted_secret: str
) -> bool:
    return (
        policy.bot_provider_key != 'cloudflare_turnstile'
        or policy.bot_site_key != (site_key or None)
        or policy.bot_hostname != (hostname or None)
        or (bool(submitted_secret) and submitted_secret != policy.bot_secret_key)
    )


def _validate_bot_enablement(
    policy: AuthenticationSecurityPolicy,
    *,
    mode: BotPolicyMode,
    site_key: str,
    effective_secret: str,
    ready: bool,
    config_changed: bool,
) -> None:
    """Keep test credentials, proof freshness and rollback as activation preconditions."""
    if mode == BotPolicyMode.ALWAYS:
        if not (current_app.debug or current_app.testing):
            if site_key in TEST_SITE_KEYS or effective_secret in TEST_SECRET_KEYS:
                db.session.rollback()
                abort(409, description='Turnstile test credentials cannot be enabled in production.')
        tested = policy.bot_tested_at
        if tested is not None and tested.tzinfo is None:
            tested = tested.replace(tzinfo=UTC)
        recent = tested is not None and timedelta(0) <= datetime.now(UTC) - tested <= timedelta(hours=1)
        if not ready or config_changed or not recent:
            db.session.rollback()
            abort(409, description='Save disabled configuration and successfully test Turnstile before enabling.')


@bp.post('/bot/policy')
@permission_required('identity_providers.manage')
def save_bot_policy():
    """Set a governed Turnstile instance with fail-closed enable validation."""
    try:
        validate_csrf(request.form.get('csrf_token'))
        mode = BotPolicyMode(str(request.form.get('bot_mode') or ''))
    except (ValidationError, ValueError):
        abort(400)
    if request.form.get('acknowledge_bot_impact') != 'yes':
        abort(400)
    if request.form.get('provider_key') != 'cloudflare_turnstile':
        abort(400)

    site_key = str(request.form.get('site_key') or '').strip()
    hostname = str(request.form.get('hostname') or '').strip().lower()
    submitted_secret = str(request.form.get('secret_key') or '')
    _validate_bot_credential_fields(site_key, hostname, submitted_secret)

    actor = cast(User, current_user._get_current_object())
    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        if policy is None:
            policy = AuthenticationSecurityPolicy()
            policy.id = 1
            policy.mfa_mode = 'disabled'
            policy.bot_mode = 'disabled'
            db.session.add(policy)
        old_mode = policy.bot_mode
        effective_secret = submitted_secret or policy.bot_secret_key or ''
        ready = _bot_configuration_qualified(site_key, hostname, effective_secret)
        config_changed = _bot_configuration_changed(policy, site_key, hostname, submitted_secret)
        _validate_bot_enablement(
            policy,
            mode=mode,
            site_key=site_key,
            effective_secret=effective_secret,
            ready=ready,
            config_changed=config_changed,
        )
        if config_changed:
            policy.bot_tested_at = None
        policy.bot_provider_key = 'cloudflare_turnstile'
        policy.bot_site_key = site_key or None
        policy.bot_hostname = hostname or None
        if submitted_secret:
            policy.bot_secret_key = submitted_secret  # EncryptedText at rest.
        policy.bot_mode = mode.value
        db.session.add(
            stage_authentication_security_event(
                actor,
                action='bot_policy_changed',
                authenticated=True,
                success=True,
                previous_mode=old_mode,
                next_mode=mode.value,
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning('Bot protection policy write was not committed.', exc_info=True)
        abort(503)
    return redirect(url_for('access.authentication_security.index', tab='bot'))


@bp.post('/bot/test')
@permission_required('identity_providers.manage')
def test_bot_provider():
    """Prove Siteverify with a real browser-issued one-use token before enable."""
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    actor = cast(User, current_user._get_current_object())
    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        if policy is None or not policy.bot_site_key or not policy.bot_secret_key or not policy.bot_hostname:
            abort(409, description='Save Turnstile configuration before testing.')
        settings = TurnstileVerificationConfig(
            secret_key=policy.bot_secret_key,
            expected_hostname=policy.bot_hostname,
            expected_action='login',
        )
        if not _configuration_ready(settings):
            abort(409, description='The Turnstile configuration is invalid.')
        if not verify_turnstile(request.form.get('cf-turnstile-response'), config=settings).passed:
            abort(409, description='Turnstile verification failed. Check keys, hostname and outbound HTTPS.')
        policy.bot_tested_at = datetime.now(UTC)
        db.session.add(
            stage_authentication_security_event(
                actor,
                action='bot_provider_verified',
                authenticated=True,
                success=True,
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning('Bot provider verification evidence could not be saved.', exc_info=True)
        abort(503)
    return redirect(url_for('access.authentication_security.index', tab='bot'))


@bp.post('/login-protection/policy')
@permission_required('identity_providers.manage')
@limiter.limit(lambda: current_app.config.get('AUTH_LOGIN_RATE_LIMIT', '5 per minute'))
def save_lockout_policy():
    destination = url_for('access.authentication_security.index', tab='bot', _anchor='login-protection-control')
    try:
        validate_csrf(request.form.get('csrf_token'))
        if request.form.get('acknowledge_lockout_impact') != 'yes':
            raise ValueError('Acknowledgement required.')
        requested = LockoutMode(request.form.get('lockout_mode', ''))
        revision = int(request.form.get('lockout_revision', ''))
        evidence = GovernanceEvidence.parse(request.form.get('ticket', ''), request.form.get('reason', ''))
        actor_id, generation = parse_authenticated_user_identifier(session.get('_user_id'))
        if not login_fresh() or actor_id != current_user.id or generation is None:
            abort(403)
    except (ValidationError, ValueError, TypeError):
        abort(400)
    try:
        changed = stage_policy_change(
            actor_id=actor_id, generation=generation, requested=requested, expected_revision=revision,
            evidence=evidence, password=request.form.get('current_password', ''),
            code=request.form.get('verification_code', ''),
        )
        db.session.commit()
    except (ValueError, LoginProtectionUnavailable):
        db.session.rollback()
        queue_transient_feedback(
            status='warning', title='Login protection not saved',
            message='Verify administrator assurance, current policy revision and activation prerequisites.',
        )
        return redirect(destination)
    except (SQLAlchemyError, CredentialEncryptionError):
        db.session.rollback()
        queue_transient_feedback(
            status='error', title='Login protection not saved', message='The security change could not be committed.',
        )
        return redirect(destination)
    queue_operational_feedback(build_operational_feedback(OperationalFeedbackSpec(
        status='success' if changed else 'info', title='Login protection updated' if changed else 'Policy unchanged',
        message='Committed policy recorded. Existing authenticated sessions are unchanged.',
        activity_audit_saved=True, notification_deck_visible=changed,
        delivery_policy=OperationalDeliveryPolicy.PERSISTENT if changed else OperationalDeliveryPolicy.AUDIT_ONLY,
    )))
    return redirect(destination)
