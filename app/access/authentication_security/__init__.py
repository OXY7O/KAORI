"""Access-owned, read-only authentication assurance review workspace (#3138)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from app.access.authentication.bot_protection.registry import bot_provider_definitions
from app.access.authentication.mfa.audit import stage_authentication_security_event
from app.access.authentication.mfa.policy import MfaPolicyMode
from app.access.authentication.mfa.service import mfa_enrolled, mfa_policy_mode
from app.extensions.db import db
from app.models import User
from app.models.authentication_security import AuthenticationSecurityPolicy
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError
from app.access.rbac.decorators import permission_required

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
    context = {
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
