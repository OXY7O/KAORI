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
    assert 'None, href) for key, label, icon, href in tabs' in source('app/access/authentication_security/__init__.py')
    assert "'Enforced' if bot_mode == 'always' else 'Not Enabled'" in template
    assert "'Configured' if bot_has_secret and bot_site_key and bot_hostname" in template
    assert 'Cloudflare Siteverify' in template
    assert 'Single active login generation' in template
    assert "url_for('access.authentication_security.save_bot_policy')" in template
    assert 'name="csrf_token"' in template
    assert 'name="acknowledge_bot_impact"' in template
    assert 'hx-post=' not in template


def test_authentication_security_submenu_uses_shared_server_route_tabs() -> None:
    template = source('app/templates/access/authentication_security/partials/_page_content.html')
    shared = source('app/templates/components/workspace_tabs.html')
    route = source('app/access/authentication_security/__init__.py')
    Environment().parse(template)
    assert 'data-authentication-security-submenu' in template
    assert 'workspace_tabs.render_navigation(' in template
    assert template.index('workspace_tabs.render_navigation(') < template.index('page_hero.shell_classes()')
    assert 'workspace_tabs.render_query_tabs(' not in template
    assert 'data-kaori-tab-variant="integrated-workspace-server"' in shared
    assert 'aria-current="page"' in shared
    assert 'href="{{ tab_href }}"' in shared
    assert 'hx-swap="outerHTML" hx-push-url="true"' in shared
    assert "hx_target='#authentication-security-page'" in template
    assert 'hx-sync="this:replace"' in template
    assert "'submenu_tabs': submenu_tabs" in route
    assert 'None, href) for key, label, icon, href in tabs' in route
    assert route.count("url_for('access.authentication_security.index', tab=key)") == 1
    assert template.count('workspace_tabs.render_navigation(') == 1


def test_authentication_security_workspace_does_not_wrap_its_standard_cards() -> None:
    page = source('app/templates/access/authentication_security/partials/_page_content.html')
    Environment().parse(page)
    assert '<section aria-label="Authentication Security Workspace"' in page
    assert 'data-auth-security-workspace="flat"' in page
    assert '<div class="space-y-4">' in page
    assert 'aria-label="Authentication Security Workspace">' not in page
    assert 'class="space-y-4 p-5 lg:p-6"' not in page
    assert page.count('assurance.render(') == 4
    assert page.index('page_hero.shell_classes()') < page.index('data-auth-security-workspace="flat"')
    assert 'workspace_tabs.render_navigation(' in page
    assert 'workspace_tabs.render_query_tabs(' not in page


def test_overview_governance_copy_stays_concise_without_truncation() -> None:
    page = source('app/templates/access/authentication_security/partials/_page_content.html')
    component = source('app/templates/access/authentication_security/partials/_assurance_summary.html')
    overview = page.split("{% if active_tab == 'overview' %}", 1)[1].split("{% elif active_tab == 'mfa' %}", 1)[0]
    for copy in (
        'Cloudflare validates Turnstile.',
        'New logins revoke old sessions.',
        'Audit tracks policy and logins.',
    ):
        assert copy in overview
    assert 'Provider Authority' in overview
    assert 'Session Revocation' in overview
    assert 'Committed Evidence' in overview
    assert 'whitespace-nowrap' not in component
    assert 'text-ellipsis' not in component
    assert 'overflow-hidden text-ellipsis' not in component
    assert 'md:grid-cols-2 xl:grid-cols-4' in component


def test_overview_control_areas_and_operational_boundaries_share_one_section() -> None:
    page = source('app/templates/access/authentication_security/partials/_page_content.html')
    Environment().parse(page)
    overview = page.split("{% if active_tab == 'overview' %}", 1)[1].split("{% elif active_tab == 'mfa' %}", 1)[0]
    assert overview.count('data-auth-security-overview-stack="true"') == 1
    assert overview.count('data-auth-security-overview-hub="true"') == 1
    assert 'data-auth-security-control-intro="above-card"' in overview
    assert 'id="auth-security-control-areas-heading"' in overview
    assert 'Authentication Security Control Areas' in overview
    assert 'Review authentication controls, ownership boundaries, and related access workspaces.' in overview
    assert overview.index('assurance.render(') < overview.index('data-auth-security-control-intro="above-card"')
    assert overview.index('id="auth-security-control-areas-heading"') < overview.index(
        'data-auth-security-overview-hub="true"'
    )
    assert overview.index('data-auth-security-overview-hub="true"') < overview.index('Review MFA Policy')
    assert overview.index('Review Session Security') < overview.index('data-auth-security-boundaries="harmonized"')
    assert 'aria-labelledby="auth-security-control-areas-heading"' in overview
    assert '<section aria-label="Authentication security controls">' in overview
    assert '<section class="border-t border-outline-subtle bg-surface-hover"' in overview
    assert 'Where security controls are governed and related account services are managed.' in overview
    assert 'class="mt-4 grid gap-4 md:grid-cols-2"' in overview
    assert (
        overview.count('flex min-w-0 flex-col rounded-xl border border-outline-default bg-surface-card p-4 lg:p-5') == 2
    )
    assert 'class="overflow-hidden rounded-xl border border-outline-default bg-surface-card"' not in overview
    for label in ('Operational Boundaries', 'Governed Here', 'Managed Elsewhere'):
        assert label in overview
    for target in ('mfa', 'bot', 'sessions'):
        assert f"tab='{target}'" in overview
    assert overview.count('Review MFA Policy') == 1
    assert overview.count('Review Bot Protection') == 1
    assert overview.count('Review Session Security') == 1
    assert 'data-auth-security-workspace="flat"' in page
    assert 'workspace_tabs.render_navigation(' in page
    assert page.count('assurance.render(') == 4


def test_overview_heading_is_text_only_and_still_above_its_control_card() -> None:
    page = source('app/templates/access/authentication_security/partials/_page_content.html')
    Environment().parse(page)
    overview = page.split("{% if active_tab == 'overview' %}", 1)[1].split("{% elif active_tab == 'mfa' %}", 1)[0]
    header = overview.split('data-auth-security-control-intro="above-card"', 1)[1].split('</header>', 1)[0]
    assert 'Authentication Security Control Areas' in header
    assert 'Review authentication controls, ownership boundaries, and related access workspaces.' in header
    assert 'data-lucide="layout-grid"' not in overview
    assert '<span' not in header
    assert overview.index('data-auth-security-control-intro="above-card"') < overview.index(
        'data-auth-security-overview-hub="true"'
    )
    assert 'data-auth-security-boundaries="harmonized"' in overview


def test_selected_tab_is_allowlisted_to_prevent_untrusted_template_selection() -> None:
    routes = source('app/access/authentication_security/__init__.py')
    assert "return requested if requested in supported else 'overview'" in routes
    for key in ('overview', 'mfa', 'bot', 'sessions'):
        assert f"('{key}'," in routes
