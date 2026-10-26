"""Authentication Security follows KAORI UI while guarding security mutations (#3137)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_authentication_security_uses_existing_access_navigation_and_rbac() -> None:
    access = source('app/access/__init__.py')
    navigation = source('app/common/workspace_navigation_catalog.py')
    breadcrumb = source('app/common/navigation.py')
    routes = source('app/access/authentication_security/__init__.py')

    assert "bp.register_blueprint(authentication_security_bp, url_prefix='/authentication-security')" in access
    assert "'authentication_security'," in navigation
    assert "'access.authentication_security.index'," in navigation
    assert "if endpoint.startswith('access.authentication_security.')" in breadcrumb
    assert "@permission_required('identity_providers.view')" in routes
    # Request dispatch remains conditionally HTMX-targeted; do not require
    # a single-line string representation of Ruff-formatted Python.
    assert "request.headers.get('HX-Request') == 'true'" in routes
    assert "request.headers.get('HX-Target') == 'authentication-security-page'" in routes
    assert "return render_template('access/authentication_security/partials/_page_content.html', **context)" in routes
    assert "return render_template('access/authentication_security/index.html', **context)" in routes


def test_authentication_security_does_not_mislabel_inactive_mfa_or_captcha() -> None:
    template = source('app/templates/access/authentication_security/partials/_page_content.html')
    index = source('app/templates/access/authentication_security/index.html')
    Environment().parse(template)
    Environment().parse(index)

    assert 'components/page_hero.html' in template
    assert 'components/workspace_tabs.html' in template
    assert 'workspace_tabs.render_navigation(' in template
    assert 'workspace_tabs.render_query_tabs(' not in template
    assert template.index('workspace_tabs.render_navigation(') < template.index('page_hero.shell_classes()')
    assert template.count('workspace_tabs.render_navigation(') == 1
    assert 'data-authentication-security-submenu' in template
    assert 'hx-sync="this:replace"' in template
    assert "prefix='authentication-security'" in template
    assert "hx_target='#authentication-security-page'" in template
    assert "'submenu_tabs': submenu_tabs" in source('app/access/authentication_security/__init__.py')
    assert "None, href) for key, label, icon, href in tabs" in source(
        'app/access/authentication_security/__init__.py'
    )
    assert "'Enforced' if bot_mode == 'always' else 'Not Enabled'" in template
    assert "'Configured' if bot_has_secret and bot_site_key and bot_hostname" in template
    assert 'Cloudflare Siteverify' in template
    assert 'Single active login generation' in template
    assert "url_for('access.authentication_security.save_bot_policy')" in template
    assert "name=\"csrf_token\"" in template
    assert "name=\"acknowledge_bot_impact\"" in template
    assert 'hx-post=' not in template


def test_authentication_security_submenu_uses_shared_server_route_tabs() -> None:
    template = source('app/templates/access/authentication_security/partials/_page_content.html')
    shared = source('app/templates/components/workspace_tabs.html')
    route = source('app/access/authentication_security/__init__.py')
    Environment().parse(template)
    assert 'data-authentication-security-submenu' in template
    assert 'workspace_tabs.render_navigation(' in template
    assert template.index('workspace_tabs.render_navigation(') < template.index(
        'page_hero.shell_classes()'
    )
    assert 'workspace_tabs.render_query_tabs(' not in template
    assert 'data-kaori-tab-variant="integrated-workspace-server"' in shared
    assert 'aria-current="page"' in shared
    assert 'href="{{ tab_href }}"' in shared
    assert 'hx-swap="outerHTML" hx-push-url="true"' in shared
    assert "hx_target='#authentication-security-page'" in template
    assert 'hx-sync="this:replace"' in template
    assert "'submenu_tabs': submenu_tabs" in route
    assert "None, href) for key, label, icon, href in tabs" in route
    assert route.count("url_for('access.authentication_security.index', tab=key)") == 1
    assert template.count('workspace_tabs.render_navigation(') == 1


def test_selected_tab_is_allowlisted_to_prevent_untrusted_template_selection() -> None:
    routes = source('app/access/authentication_security/__init__.py')
    assert "return requested if requested in supported else 'overview'" in routes
    for key in ('overview', 'mfa', 'bot', 'sessions'):
        assert f"('{key}'," in routes
