"""Access-owned, read-only authentication assurance review workspace (#3138)."""

from __future__ import annotations

from flask import Blueprint, render_template, request, url_for

from app.access.authentication.bot_protection.registry import bot_provider_definitions
from app.access.authentication.mfa.policy import MfaPolicyMode
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
        (key, label, icon, url_for('access.authentication_security.index', tab=key))
        for key, label, icon in _TABS
    )
    context = {
        'active_tab': active_tab,
        'tabs': tabs,
        'mfa_modes': tuple(mode.value for mode in MfaPolicyMode),
        'bot_providers': bot_provider_definitions(),
    }
    if request.headers.get('HX-Request') == 'true' and request.headers.get('HX-Target') == 'authentication-security-page':
        return render_template('access/authentication_security/partials/_page_content.html', **context)
    return render_template('access/authentication_security/index.html', **context)
