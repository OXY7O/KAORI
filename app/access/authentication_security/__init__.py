"""Access-owned Authentication Security policy and provider management."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.authentication.bot_protection.registry import bot_provider_definitions
from app.access.authentication.bot_protection.service import BotPolicyMode
from app.access.authentication.bot_protection.turnstile import TurnstileVerificationConfig, _configuration_ready
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaPolicyMode
from app.access.authentication.mfa.service import mfa_enrolled, mfa_policy_mode
from app.access.rbac.decorators import permission_required
from app.extensions.db import db
from app.models import User
from app.models.authentication_security import AuthenticationSecurityPolicy

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
    """Change committed MFA policy and revoke previously issued login sessions."""
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
        if previous != requested.value:
            policy.mfa_mode = requested.value
            # Changing the effective assurance level invalidates pre-policy
            # sessions as a single atomic DB transaction, including Remember Me.
            db.session.execute(
                update(User)
                .where(User.account_is_active.is_(True), User.deleted_at.is_(None))
                .values(auth_session_version=func.coalesce(User.auth_session_version, 1) + 1)
            )
            db.session.add(stage_authentication_security_event(
                actor, action='mfa_policy_changed', authenticated=True, success=True,
                previous_mode=previous, next_mode=requested.value,
            ))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.warning('MFA policy change was not committed.', exc_info=True)
        abort(503)
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
        if mode == BotPolicyMode.ALWAYS and not ready:
            db.session.rollback()
            abort(409, description='A valid site key, hostname and secret are required to enable Turnstile.')
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
