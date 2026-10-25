"""Authentication Security full-cycle UI preserves KAORI shared navigation and RBAC."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_authentication_security_reuses_existing_access_navigation_and_guards() -> None:
    access = source('app/access/__init__.py')
    navigation = source('app/common/workspace_navigation_catalog.py')
    breadcrumb = source('app/common/navigation.py')
    routes = source('app/access/authentication_security/__init__.py')

    assert "bp.register_blueprint(authentication_security_bp, url_prefix='/authentication-security')" in access
    assert "'authentication_security'," in navigation
    assert "'access.authentication_security.index'," in navigation
    assert "if endpoint.startswith('access.authentication_security.')" in breadcrumb
    assert "@permission_required('identity_providers.view')" in routes
    assert "@permission_required('identity_providers.manage')" in routes
    assert "'HX-Target') == 'authentication-security-page'" in routes


def test_authentication_security_uses_existing_violet_htmx_and_explicit_state() -> None:
    template = source('app/templates/access/authentication_security/partials/_page_content.html')
    index = source('app/templates/access/authentication_security/index.html')
    Environment().parse(template)
    Environment().parse(index)

    assert 'components/page_hero.html' in template
    assert 'components/workspace_tabs.html' in template
    assert 'workspace_tabs.render_query_tabs(' in template
    assert "hx_target='#authentication-security-page'" in template
    assert 'mfa_policy_mode' in template
    assert 'bot_state.configured' in template
    assert "table_label.status_indicator_label('Enforced' if bot_state.required else 'Not Enabled'" in template
    assert "url_for('access.authentication_security.save_mfa_policy')" in template
    assert "url_for('access.authentication_security.save_bot_provider')" in template
    assert 'name="csrf_token"' in template
    assert 'Single active login generation' in template
    assert 'hx-post=' not in template


def test_selected_tab_is_allowlisted_and_provider_secret_never_rendered() -> None:
    routes = source('app/access/authentication_security/__init__.py')
    template = source('app/templates/access/authentication_security/partials/_page_content.html')
    assert "return requested if requested in supported else 'overview'" in routes
    for key in ('overview', 'mfa', 'bot', 'sessions'):
        assert f"('{key}'," in routes
    assert 'bot_secret' not in template
    assert 'policy.bot_secret' not in template
    assert 'type="password"' in template


def test_authentication_security_requires_persistence_and_gates_at_login() -> None:
    models = source('app/models/authentication_security.py')
    routes = source('app/access/authentication/routes.py')
    settings = source('app/settings/routes.py')
    assert "Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)" in models
    assert "mapped_column(EncryptedText(), nullable=False)" in models
    assert "mapped_column(EncryptedText(), nullable=True)" in models
    assert "mfa_verified: bool = False" in routes
    assert "MFA_PENDING_SESSION_KEY" in routes
    assert "verify_mfa_challenge(user, str(form.verification_code.data or ''))" in routes
    assert "verify_bot_challenge(bot_policy, request.form.get('cf-turnstile-response'))" in routes
    assert "active_tab not in {'profile', 'activity', 'credentials', 'mfa'}" in settings
