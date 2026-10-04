from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'sidebar.html'
MODEL = ROOT / 'app' / 'common' / 'workspace_navigation.py'
CATALOG = ROOT / 'app' / 'common' / 'workspace_navigation_catalog.py'
LAYOUT = ROOT / 'app' / 'templates' / 'layouts' / 'app.html'
PRESENTATION = ROOT / 'app' / 'bootstrap' / 'presentation.py'
BREADCRUMB = ROOT / 'app' / 'common' / 'navigation.py'
SIDEBAR_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'SIDEBAR_NAVIGATION.md'
WORKSPACE_STANDARD = ROOT / 'docs' / 'design' / 'components' / 'DOMAIN_WORKSPACE_NAVIGATION.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f'Missing navigation contract file: {path.relative_to(ROOT)}')
    return path.read_text(encoding='utf-8')


def _require(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f'{owner}: missing tokens: {", ".join(missing)}')


def verify() -> None:
    sidebar = _read(SIDEBAR)
    model = _read(MODEL)
    catalog = _read(CATALOG)
    semantic_model = f'{model}\n{catalog}'
    layout = _read(LAYOUT)
    presentation = _read(PRESENTATION)
    breadcrumb = _read(BREADCRUMB)
    sidebar_standard = _read(SIDEBAR_STANDARD)
    workspace_standard = _read(WORKSPACE_STANDARD)

    _require(
        sidebar,
        (
            'w-[250px]',
            'lg:[.sidebar-collapsed_&]:w-[78px]',
            'data-kaori-sidebar-section',
            'data-kaori-sidebar-workspace',
            'data-kaori-sidebar-workspace-trigger',
            'data-kaori-sidebar-capabilities',
            'data-kaori-sidebar-capability',
            "{% if item['children'] %}",
            "{% for child in item['children'] %}",
            "child['href']",
            "child['label']",
            "child['active']",
            '<details class="sidebar-menu space-y-1"',
            'sidebar-parent-active',
            'sidebar-submenu',
            'min-h-11',
            'text-base font-semibold leading-6',
            'text-sm leading-5',
        ),
        'two-level sidebar renderer',
    )

    if 'section.items' in sidebar:
        raise AssertionError("sidebar renderer must use section['items'], not dict.items attribute lookup")
    if 'workspace_tabs.render_navigation' in sidebar:
        raise AssertionError('sidebar capabilities must not be rendered as horizontal workspace tabs')

    for legacy in (
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
    ):
        if legacy in sidebar:
            raise AssertionError(f'legacy sidebar include remains active: {legacy}')

    _require(
        semantic_model,
        (
            'class WorkspaceCapabilityDefinition:',
            'capabilities: tuple[WorkspaceCapabilityDefinition, ...]',
            'def build_sidebar_navigation(',
            'def build_capability_navigation(',
            "'children': children",
            "'children': ()",
            "'active': (",
            '_visible_capabilities',
            '_resolved_capability_endpoint',
            '_active_capability_key',
            "'kubernetes_operations.create_configmap': 'configmaps'",
            "'kubernetes_operations.update_configmap': 'configmaps'",
            "'kubernetes_operations.delete_configmap': 'configmaps'",
            "'kubernetes_operations': 'secrets'",
            '_WORKSPACE_CONTEXT_KEYS',
            '_CAPABILITY_CONTEXT_KEYS',
            '_preserved_context',
            "key='kubernetes'",
            "key='object_storage'",
            "key='intelligence'",
            "key='reports'",
            "key='operations_center'",
            "key='integrations'",
            "key='access'",
            "key='settings'",
        ),
        'navigation semantic model',
    )

    if 'def build_workspace_navigation(' in model:
        raise AssertionError('horizontal Domain Workspace navigation model must not remain active')

    for future_placeholder in (
        "key='compute'",
        "key='network'",
        "key='reliability'",
        "key='finops'",
        "key='automation'",
        "key='backup_recovery'",
    ):
        if future_placeholder in semantic_model:
            raise AssertionError(f'reserved future workspace rendered as placeholder: {future_placeholder}')

    _require(
        presentation,
        (
            "'sidebar_navigation': build_sidebar_navigation(request.endpoint, current_user, request.args)",
            "'capability_navigation': build_capability_navigation(request.endpoint, current_user, request.args)",
        ),
        'presentation context',
    )
    if "'workspace_navigation':" in presentation or 'build_workspace_navigation' in presentation:
        raise AssertionError('presentation still publishes retired horizontal workspace navigation')

    navbar = _read(ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'navbar.html')
    navbar_js = _read(ROOT / 'app' / 'static' / 'js' / 'navbar.js')
    if "namespace(label='Welcome')" in navbar:
        raise AssertionError(
            'navbar mobile label must not call the Jinja namespace() builtin because route context may own a namespace variable'
        )
    _require(
        navbar,
        (
            "mobile_page_candidates = breadcrumb_items | rejectattr('label', 'equalto', 'KAORI') | list",
            "mobile_page_label = mobile_page_candidates[-1].label if mobile_page_candidates else 'Welcome'",
            "desktop_breadcrumb_items = breadcrumb_items | rejectattr('label', 'equalto', 'KAORI') | list",
            'breadcrumb_compacted = desktop_breadcrumb_items|length > 3',
            'breadcrumb_hidden_items = desktop_breadcrumb_items[1:-1] if breadcrumb_compacted else []',
            'surface_ui.block_classes(allow_overflow=true)',
            'max-w-[9rem]',
            'max-w-[12rem]',
            'data-breadcrumb-overflow-trigger',
            'aria-controls="breadcrumb-overflow-path"',
            ':aria-expanded="breadcrumbOpen.toString()"',
            '@click.outside="breadcrumbOpen = false"',
            '{{ mobile_page_label }}',
        ),
        'navbar bounded breadcrumb renderer',
    )
    _require(
        navbar_js,
        (
            'breadcrumbOpen: false',
            'breadcrumbReturnTarget: null',
            'toggleBreadcrumb()',
            'const breadcrumbReturnTarget = this.breadcrumbOpen ? this.breadcrumbReturnTarget : null',
            'this.breadcrumbOpen = false',
            'this.restoreFocus(breadcrumbReturnTarget)',
        ),
        'navbar breadcrumb disclosure behavior',
    )

    _require(
        layout,
        (
            '{% import "components/workspace_tabs.html" as workspace_tabs %}',
            'data-kaori-capability-navigation="{{ capability_navigation.key }}"',
            'workspace_tabs.render_navigation(',
            "prefix='detail-' ~ capability_navigation.key",
        ),
        'page level-3 navigation',
    )
    for retired in (
        'data-kaori-domain-workspace-nav',
        'workspace_navigation',
    ):
        if retired in layout:
            raise AssertionError(f'app shell retains retired horizontal workspace navigation: {retired}')

    _require(
        breadcrumb,
        (
            "BreadcrumbItem('Kubernetes', 'boxes')",
            "BreadcrumbItem('Object Storage', 'database')",
            "BreadcrumbItem('Inventory')",
            "BreadcrumbItem('Operations')",
            "BreadcrumbItem('Analytics', 'chart-no-axes-combined')",
        ),
        'breadcrumb hierarchy',
    )

    _require(
        sidebar_standard,
        (
            '# KAORI Sidebar Navigation Standard v2.2',
            'Level 1 — Workspace / Domain',
            'Level 2 — Capability',
            'a third nested sidebar level is prohibited',
            'Reserved Future Ownership',
            'no horizontal Domain Workspace strip',
            '5 levels including `KAORI`',
            '4 visible breadcrumb items',
            'maximum width of **9rem**',
            'maximum width of **12rem**',
        ),
        'sidebar v2.2 documentation',
    )

    _require(
        workspace_standard,
        (
            '# KAORI Page Workspace Navigation Standard v1.1',
            'Page level 3 — Detailed View / Resource View',
            'There is **no global Domain Workspace horizontal strip**',
            'components/workspace_tabs.html',
            'Analytics Overview always keeps the route-level Integrated Workspace Tabs visible',
        ),
        'page workspace documentation',
    )

    quality_gate = _read(QUALITY_GATE)
    if 'python scripts/verify_sidebar_navigation_standard.py' not in quality_gate:
        raise AssertionError('quality gate does not execute the sidebar standard verifier')

    print(
        'KAORI sidebar navigation standard passed: two-level Workspace -> Capability sidebar, '
        'bounded breadcrumb compression, page-owned level-3 detail navigation, permission-aware disclosure, '
        'and future-domain guardrails are locked.'
    )


if __name__ == '__main__':
    verify()
