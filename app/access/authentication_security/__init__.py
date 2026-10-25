"""Access-owned Authentication Security policy and provider management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.authentication.bot_protection.registry import bot_provider_definitions
from app.access.authentication.bot_protection.service import BotPolicyMode, TEST_SECRET_KEYS, TEST_SITE_KEYS
from app.access.authentication.bot_protection.turnstile import (
    TurnstileVerificationConfig,
    _configuration_ready,
    verify_turnstile,
)
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaPolicyMode
from app.access.authentication.mfa.service import mfa_enrolled, mfa_policy_mode
from app.access.authentication.session import clear_authenticated_session
from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.models import User
from app.models.authentication_security import AuthenticationSecurityPolicy
from app.platform_operations.notifications.service import queue_transient_feedback

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
    row = db.session.get(AuthenticationSecurityPolicy, 1)
    context = {
        'bot_mode': row.bot_mode if row is not None else 'disabled',
        'bot_provider_key': row.bot_provider_key if row is not None else 'cloudflare_turnstile',
        'bot_site_key': row.bot_site_key if row is not None else '',
        'bot_hostname': row.bot_hostname if row is not None else '',
        'bot_has_secret': bool(row is not None and row.bot_secret_key),
        'bot_tested_at': row.bot_tested_at if row is not None else None,
        'active_tab': active_tab,
        'tabs': tabs,
        'mfa_modes': tuple(mode.value for mode in MfaPolicyMode),
        'mfa_policy_mode': mfa_policy_mode(),
        'can_manage_authentication_security': current_user.has_permission('identity_providers.manage'),
        'bot_providers': bot_provider_definitions(),
    }
    if (
        request.headers.get('HX-Request') == 'true'
        and request.headers.get('HX-Target') == 'authentication-security-page'
    ):
        return render_template('access/authentication_security/partials/_page_content.html', **context)
    return render_template('access/authentication_security/index.html', **context)


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

    actor = current_user._get_current_object()
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
            policy = AuthenticationSecurityPolicy(id=1, mfa_mode='disabled')
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
        queue_transient_feedback(
            status='success',
            title='MFA policy updated',
            message='MFA policy saved and existing sessions revoked; sign in again to continue.',
        )
        return redirect(url_for('auth.login'))

    # An unchanged selection is an audited user action, not a policy transition.
    # Do not revoke sessions or claim the configuration changed.
    queue_transient_feedback(
        status='info',
        title='MFA policy unchanged',
        message='The selected MFA policy is already active; no sessions were revoked.',
    )
    return redirect(url_for('access.authentication_security.index', tab='mfa'))

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
    if len(site_key) > 255 or len(hostname) > 253 or len(submitted_secret) > 256:
        abort(400)
    if submitted_secret and any(char.isspace() for char in submitted_secret):
        abort(400)

    actor = current_user._get_current_object()
    try:
        policy = db.session.get(AuthenticationSecurityPolicy, 1, with_for_update=True)
        if policy is None:
            policy = AuthenticationSecurityPolicy(id=1, mfa_mode='disabled', bot_mode='disabled')
            db.session.add(policy)
        old_mode = policy.bot_mode
        effective_secret = submitted_secret or policy.bot_secret_key or ''
        candidate = TurnstileVerificationConfig(
            secret_key=effective_secret, expected_hostname=hostname, expected_action='login'
        )
        ready = bool(
            site_key
            and site_key.isascii()
            and not any(char.isspace() for char in site_key)
            and _configuration_ready(candidate)
        )
        config_changed = (
            policy.bot_provider_key != 'cloudflare_turnstile'
            or policy.bot_site_key != (site_key or None)
            or policy.bot_hostname != (hostname or None)
            or (bool(submitted_secret) and submitted_secret != policy.bot_secret_key)
        )
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
    actor = current_user._get_current_object()
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
