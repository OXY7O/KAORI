from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def _navigation_source() -> str:
    return _read('app/common/workspace_navigation.py') + '\n' + _read('app/common/workspace_navigation_catalog.py')


def test_sidebar_navigation_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_sidebar_navigation_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI sidebar navigation standard passed' in result.stdout


def test_sidebar_v21_uses_two_real_levels_below_section_groups() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')
    model = _navigation_source()

    assert '<details class="sidebar-menu space-y-1"' in sidebar
    assert 'data-kaori-sidebar-workspace="{{ item[\'key\'] }}"' in sidebar
    assert 'data-kaori-sidebar-workspace-trigger="{{ item[\'key\'] }}"' in sidebar
    assert 'data-kaori-sidebar-capability="{{ child[\'key\'] }}"' in sidebar
    assert "{% for child in item['children'] %}" in sidebar
    assert 'sidebar-submenu' in sidebar

    assert 'class WorkspaceCapabilityDefinition:' in model
    assert 'capabilities: tuple[WorkspaceCapabilityDefinition, ...]' in model
    assert "'children': children" in model
    assert "'children': ()" in model
    assert 'def build_workspace_navigation(' not in model


def test_sidebar_mapping_access_avoids_jinja_dict_method_collisions() -> None:
    sidebar = _read('app/templates/components/navigation/sidebar.html')

    assert "{% for item in section['items'] %}" in sidebar
    assert 'section.items' not in sidebar
    for key in ('label', 'key', 'active', 'icon', 'children'):
        assert f"item['{key}']" in sidebar
    for key in ('href', 'label', 'key', 'active', 'icon'):
        assert f"child['{key}']" in sidebar


def test_current_workspace_capabilities_are_sidebar_children() -> None:
    model = _navigation_source()

    for workspace in (
        "key='kubernetes'",
        "key='object_storage'",
        "key='intelligence'",
        "key='reports'",
        "key='operations_center'",
        "key='integrations'",
        "key='access'",
        "key='settings'",
    ):
        assert workspace in model

    for capability in (
        "'overview', 'Overview'",
        "'inventory', 'Inventory'",
        "'operations',",
        "'governance', 'Governance'",
        "'tenant', 'Tenant'",
        "'analytics', 'Analytics'",
        "'recommendations', 'Recommendations'",
        "'alert_intelligence',",
        "'generate',",
        "'data_lifecycle',",
        "'identity_providers',",
    ):
        assert capability in model

    for future in (
        "key='compute'",
        "key='network'",
        "key='reliability'",
        "key='finops'",
        "key='automation'",
    ):
        assert future not in model


def test_app_shell_renders_only_page_level_integrated_route_navigation() -> None:
    layout = _read('app/templates/layouts/app.html')
    presentation = _read('app/bootstrap/presentation.py')

    assert 'data-kaori-domain-workspace-nav' not in layout
    assert 'workspace_navigation' not in layout
    assert 'workspace_tabs.render_navigation(' in layout
    assert 'build_workspace_navigation' not in presentation
    assert "'workspace_navigation':" not in presentation

    assert '{% import "components/workspace_tabs.html" as workspace_tabs %}' in layout
    assert 'data-kaori-capability-navigation="{{ capability_navigation.key }}"' in layout
    assert 'workspace_tabs.render_navigation(' in layout
    assert "prefix='detail-' ~ capability_navigation.key" in layout


def test_level_three_detail_navigation_replaces_sidebar_level_three() -> None:
    model = _navigation_source()
    layout = _read('app/templates/layouts/app.html')

    for capability in (
        "'kubernetes_inventory': (",
        "'kubernetes_operations': (",
        "'kubernetes_governance': (",
        "'kubernetes_tenant': (",
        "'kubernetes_analytics': (",
        "'object_storage_inventory': (",
        "'object_storage_analytics': (",
    ):
        assert capability in model

    assert "'Topology', 'waypoints', 'inventory.topology'" in model
    assert "'Nodes', 'server', 'inventory.nodes'" in model
    assert "'ConfigMaps'," in model
    assert "'Secrets'," in model
    assert "'TLS Certificates'," in model
    assert "'Resource Profiles'," in model
    assert "'Buckets & Containers'," in model
    assert "'Capacity & Usage'," in model
    assert 'workspace_tabs.render_navigation(' in layout


def test_kubernetes_operations_workflows_keep_the_correct_active_detail_tab() -> None:
    model = _navigation_source()

    for endpoint in ('create_configmap', 'update_configmap', 'delete_configmap'):
        assert f"'kubernetes_operations.{endpoint}': 'configmaps'" in model
    assert "'kubernetes_operations': 'secrets'" in model


def test_navigation_context_is_preserved_without_becoming_navigation_identity() -> None:
    model = _navigation_source()
    presentation = _read('app/bootstrap/presentation.py')

    assert "'kubernetes': ('cluster_id',)" in model
    assert "'object_storage': ('system_id',)" in model
    assert "'kubernetes_analytics': ('cluster_id', 'time_range')" in model
    assert "'object_storage_analytics': ('system_id', 'time_range')" in model
    assert "'kubernetes_operations': ('cluster_id', 'namespace')" in model
    assert '_preserved_context' in model
    assert 'build_sidebar_navigation(request.endpoint, current_user, request.args)' in presentation
    assert 'build_capability_navigation(request.endpoint, current_user, request.args)' in presentation


def test_analytics_overview_keeps_route_navigation_and_subordinate_summary_tabs() -> None:
    model = _navigation_source()
    overview = _read('app/templates/kubernetes/analytics/overview/index.html')

    assert "capability_key == 'kubernetes_analytics' and resolved_endpoint == 'analytics.overview'" not in model
    assert '{% block page_capability_navigation %}' not in overview
    assert "content_tabs.render_buttons('overview-content'" in overview


def test_navigation_documentation_registers_corrected_hierarchy() -> None:
    sidebar_standard = _read('docs/design/components/SIDEBAR_NAVIGATION.md')
    workspace_standard = _read('docs/design/components/DOMAIN_WORKSPACE_NAVIGATION.md')
    design_system = _read('docs/design/DESIGN_SYSTEM.md')
    ownership = _read('docs/design/components/REUSABLE_COMPONENT_OWNERSHIP.md')

    assert 'KAORI Sidebar Navigation Standard v2.1' in sidebar_standard
    assert 'Level 1 — Workspace / Domain' in sidebar_standard
    assert 'Level 2 — Capability' in sidebar_standard
    assert 'KAORI Page Workspace Navigation Standard v1.1' in workspace_standard
    assert 'Page level 3 — Detailed View / Resource View' in workspace_standard
    assert 'two-level Workspace → Capability sidebar navigation contract' in design_system
    assert '`app/common/workspace_navigation.py`' in ownership


def test_navbar_mobile_label_does_not_use_jinja_namespace_builtin() -> None:
    navbar = _read('app/templates/components/navigation/navbar.html')

    assert "namespace(label='Welcome')" not in navbar
    assert "mobile_page_candidates = breadcrumb_items | rejectattr('label', 'equalto', 'KAORI') | list" in navbar
    assert "mobile_page_label = mobile_page_candidates[-1].label if mobile_page_candidates else 'Welcome'" in navbar
    assert '{{ mobile_page_label }}' in navbar


def test_breadcrumb_hierarchy_matches_workspace_capability_detail_scope() -> None:
    breadcrumb = _read('app/common/navigation.py')

    assert "BreadcrumbItem('Kubernetes', 'boxes')" in breadcrumb
    assert "BreadcrumbItem('Object Storage', 'database')" in breadcrumb
    assert "BreadcrumbItem('Inventory')" in breadcrumb
    assert "BreadcrumbItem('Operations')" in breadcrumb
    assert "BreadcrumbItem('Analytics', 'chart-no-axes-combined')" in breadcrumb
    assert "BreadcrumbItem('Dashboards', 'layout-dashboard')" not in breadcrumb


def test_level_three_integrated_workspace_tabs_do_not_float() -> None:
    layout = _read('app/templates/layouts/app.html')
    workspace_tabs = _read('app/templates/components/workspace_tabs.html')
    content_tabs = _read('app/templates/components/content_tabs.html')

    assert 'workspace_tabs.render_navigation(' in layout
    assert 'content_tabs.render_links(' not in layout
    assert 'data-kaori-tab-variant="integrated-workspace-server"' in workspace_tabs
    assert 'overflow-x-auto border-b border-outline-subtle' in workspace_tabs
    assert 'rounded-xl border border-outline-default bg-surface-card' in content_tabs


def test_kubernetes_analytics_overview_always_uses_layout_route_navigation() -> None:
    layout = _read('app/templates/layouts/app.html')
    model = _navigation_source()
    overview = _read('app/templates/kubernetes/analytics/overview/index.html')

    assert '{% block page_capability_navigation %}' in layout
    assert "capability_key == 'kubernetes_analytics' and resolved_endpoint == 'analytics.overview'" not in model
    assert '{% block page_capability_navigation %}' not in overview
    assert "content_tabs.render_buttons('overview-content'" in overview
