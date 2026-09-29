from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'sidebar.html'
WORKSPACE_MODEL = ROOT / 'app' / 'common' / 'workspace_navigation.py'
BREADCRUMB = ROOT / 'app' / 'common' / 'navigation.py'
LAYOUT = ROOT / 'app' / 'templates' / 'layouts' / 'app.html'
PRESENTATION = ROOT / 'app' / 'bootstrap' / 'presentation.py'
SIDEBAR_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'SIDEBAR_NAVIGATION.md'
WORKSPACE_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'DOMAIN_WORKSPACE_NAVIGATION.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f'Missing required navigation contract file: {path.relative_to(ROOT)}')
    return path.read_text(encoding='utf-8')


def _require_tokens(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f'{owner}: missing canonical tokens: {", ".join(missing)}')


def verify() -> None:
    sidebar = _read(SIDEBAR)
    workspace_model = _read(WORKSPACE_MODEL)
    breadcrumb = _read(BREADCRUMB)
    layout = _read(LAYOUT)
    presentation = _read(PRESENTATION)
    sidebar_standard = _read(SIDEBAR_STANDARD)
    workspace_standard = _read(WORKSPACE_STANDARD)

    _require_tokens(
        sidebar,
        (
            'w-[250px]',
            'lg:[.sidebar-collapsed_&]:w-[78px]',
            'rounded-2xl',
            'bg-surface-sidebar',
            'overflow-y-auto',
            'sidebar-expanded-only',
            'text-sm font-extrabold leading-5',
            'text-xs font-medium',
            'data-kaori-sidebar-section',
            'data-kaori-sidebar-workspace',
            "{% for item in section['items'] %}",
            "item['href']",
            "item['label']",
            "item['key']",
            "item['active']",
            "item['icon']",
            'aria-current="page"',
            'sidebar-parent-link',
            'min-h-11',
            'text-base font-semibold leading-6',
        ),
        'sidebar v2 shell',
    )

    if '<details class="sidebar-menu' in sidebar:
        raise AssertionError('sidebar.html: v2 global navigation must not render expandable nested menus')

    if 'section.items' in sidebar:
        raise AssertionError(
            "sidebar.html: Jinja mapping key 'items' must use explicit bracket access; "
            "attribute lookup resolves dict.items() instead of the navigation collection"
        )

    legacy_includes = (
        'dashboards_menu.html',
        'inventory_menu.html',
        'kubernetes_operations_menu.html',
        'governance_menu.html',
        'tenant_menu.html',
        'object_storage_menu.html',
        'analytics_menu.html',
        'intelligence_menu.html',
        'reports_menu.html',
        'platform_operations_menu.html',
        'integrations_menu.html',
        'access_management_menu.html',
        'settings_menu.html',
    )
    for filename in legacy_includes:
        if filename in sidebar:
            raise AssertionError(f'sidebar.html: legacy nested menu include remains active: {filename}')

    _require_tokens(
        workspace_model,
        (
            "_SECTION_ORDER = ('Main', 'Infrastructure', 'Operations', 'Assurance', 'Insights', 'Platform', 'Administration')",
            "key='kubernetes'",
            "key='object_storage'",
            "key='intelligence'",
            "key='reports'",
            "key='operations_center'",
            "key='integrations'",
            "key='access'",
            "key='settings'",
            "'Overview', 'layout-dashboard', 'kubernetes_dashboard.index'",
            "'Inventory', 'boxes', 'inventory.overview'",
            "'Tenant', 'building-2', 'tenant.index'",
            "'Analytics', 'chart-column', 'analytics.overview'",
            "'Inventory', 'database', 'object_storage_inventory.overview'",
            "'Analytics', 'chart-column', 'analytics.object_storage_overview'",
            '_resolved_tab_endpoint',
            'build_sidebar_navigation',
            'build_workspace_navigation',
            'build_capability_navigation',
            '_preserved_context',
            "_WORKSPACE_CONTEXT_KEYS",
            "_CAPABILITY_CONTEXT_KEYS",
            "capability_key == 'kubernetes_analytics' and resolved_endpoint == 'analytics.overview'",
            "'kubernetes_inventory': (",
            "'kubernetes_operations': (",
            "'kubernetes_governance': (",
            "'kubernetes_tenant': (",
            "'kubernetes_analytics': (",
            "'object_storage_inventory': (",
            "'object_storage_analytics': (",
        ),
        'workspace navigation model',
    )

    for future_placeholder in (
        "key='compute'",
        "key='network'",
        "key='reliability'",
        "key='finops'",
        "key='automation'",
        "key='backup_recovery'",
    ):
        if future_placeholder in workspace_model:
            raise AssertionError(f'workspace navigation model renders reserved future placeholder: {future_placeholder}')

    _require_tokens(
        presentation,
        (
            'build_sidebar_navigation',
            'build_workspace_navigation',
            "'sidebar_navigation': build_sidebar_navigation(request.endpoint, current_user)",
            "'workspace_navigation': build_workspace_navigation(request.endpoint, current_user, request.args)",
            "'capability_navigation': build_capability_navigation(request.endpoint, current_user, request.args)",
        ),
        'presentation context',
    )

    _require_tokens(
        layout,
        (
            '{% import "components/workspace_tabs.html" as workspace_tabs %}',
            'data-kaori-domain-workspace-nav="{{ workspace_navigation.key }}"',
            'workspace_tabs.render_navigation(',
            "prefix='domain-' ~ workspace_navigation.key",
            '{% import "components/content_tabs.html" as content_tabs %}',
            'data-kaori-capability-navigation="{{ capability_navigation.key }}"',
            'content_tabs.render_links(',
        ),
        'domain workspace renderer',
    )

    _require_tokens(
        breadcrumb,
        (
            "BreadcrumbItem('Kubernetes', 'boxes')",
            "BreadcrumbItem('Object Storage', 'database')",
            "BreadcrumbItem('Inventory')",
            "BreadcrumbItem('Operations')",
            "BreadcrumbItem('Analytics', 'chart-no-axes-combined')",
        ),
        'breadcrumb v2 ownership',
    )
    for obsolete in (
        "BreadcrumbItem('Dashboards', 'layout-dashboard')",
        "BreadcrumbItem('Inventory', 'boxes')",
        "BreadcrumbItem('Analytics', 'chart-no-axes-combined'),\n            BreadcrumbItem('Kubernetes'",
    ):
        if obsolete in breadcrumb:
            raise AssertionError(f'navigation breadcrumb retains obsolete mixed-root ownership: {obsolete}')

    _require_tokens(
        sidebar_standard,
        (
            '# KAORI Sidebar Navigation Standard v2.0',
            'Section -> Workspace',
            'A third level in the global sidebar is prohibited.',
            'Reserved future ownership',
            'Empty future sections are not rendered.',
            'scripts/verify_sidebar_navigation_standard.py',
        ),
        'sidebar v2 documentation',
    )

    _require_tokens(
        workspace_standard,
        (
            '# KAORI Domain Workspace Navigation Standard v1.0',
            'Workspace -> Capability',
            'workspace_tabs.render_navigation()',
            'Context Is Not Navigation',
            'Reserved Future Workspace Contracts',
            'Playwright Evidence',
        ),
        'domain workspace documentation',
    )

    quality_gate = _read(QUALITY_GATE)
    if 'python scripts/verify_sidebar_navigation_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the sidebar standard verifier')

    print(
        'KAORI sidebar navigation standard passed: v2 Section -> Workspace global navigation, '
        'shared Domain Workspace navigation, breadcrumb ownership, permission-aware roots, and future-placeholder guardrails are locked.'
    )


if __name__ == '__main__':
    verify()
