from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


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


def test_sidebar_v2_and_domain_workspace_authorities_are_registered() -> None:
    readme = (ROOT / 'docs' / 'design' / 'README.md').read_text(encoding='utf-8')
    design_system = (ROOT / 'docs' / 'design' / 'DESIGN_SYSTEM.md').read_text(encoding='utf-8')
    sidebar_standard = (ROOT / 'docs' / 'design' / 'components' / 'SIDEBAR_NAVIGATION.md').read_text(
        encoding='utf-8'
    )
    workspace_standard = (
        ROOT / 'docs' / 'design' / 'components' / 'DOMAIN_WORKSPACE_NAVIGATION.md'
    ).read_text(encoding='utf-8')
    ownership = (
        ROOT / 'docs' / 'design' / 'components' / 'REUSABLE_COMPONENT_OWNERSHIP.md'
    ).read_text(encoding='utf-8')

    assert 'locked application-shell navigation contract' in readme
    assert 'DOMAIN_WORKSPACE_NAVIGATION.md' in readme
    assert 'locked v2 global Section → Workspace' in design_system
    assert 'KAORI Sidebar Navigation Standard v2.0' in sidebar_standard
    assert 'A third level in the global sidebar is prohibited.' in sidebar_standard
    assert 'KAORI Domain Workspace Navigation Standard v1.0' in workspace_standard
    assert 'workspace_tabs.render_navigation()' in workspace_standard
    assert '`app/common/workspace_navigation.py`' in ownership


def test_global_sidebar_is_workspace_only_and_future_domains_are_not_placeholders() -> None:
    sidebar = (ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'sidebar.html').read_text(
        encoding='utf-8'
    )
    model = (ROOT / 'app' / 'common' / 'workspace_navigation.py').read_text(encoding='utf-8')

    assert 'data-kaori-sidebar-section' in sidebar
    assert 'data-kaori-sidebar-workspace' in sidebar
    assert '<details class="sidebar-menu' not in sidebar
    assert 'analytics_menu.html' not in sidebar
    assert 'inventory_menu.html' not in sidebar
    assert 'tenant_menu.html' not in sidebar

    for current in (
        "key='kubernetes'",
        "key='object_storage'",
        "key='intelligence'",
        "key='reports'",
        "key='operations_center'",
        "key='integrations'",
        "key='access'",
        "key='settings'",
    ):
        assert current in model

    for future in ("key='compute'", "key='network'", "key='reliability'", "key='finops'", "key='automation'"):
        assert future not in model


def test_domain_workspace_navigation_reuses_integrated_workspace_tabs() -> None:
    layout = (ROOT / 'app' / 'templates' / 'layouts' / 'app.html').read_text(encoding='utf-8')
    model = (ROOT / 'app' / 'common' / 'workspace_navigation.py').read_text(encoding='utf-8')

    assert '{% import "components/workspace_tabs.html" as workspace_tabs %}' in layout
    assert 'workspace_tabs.render_navigation(' in layout
    assert 'data-kaori-domain-workspace-nav="{{ workspace_navigation.key }}"' in layout

    for kubernetes_tab in (
        "'overview', 'Overview'",
        "'inventory', 'Inventory'",
        "'operations',",
        "'governance', 'Governance'",
        "'tenant', 'Tenant'",
        "'analytics', 'Analytics'",
    ):
        assert kubernetes_tab in model

    assert "'object_storage'" in model
    assert "'object_storage_inventory.overview'" in model
    assert "'analytics.object_storage_overview'" in model


def test_breadcrumb_hierarchy_matches_workspace_ownership() -> None:
    breadcrumb = (ROOT / 'app' / 'common' / 'navigation.py').read_text(encoding='utf-8')

    assert "BreadcrumbItem('Kubernetes', 'boxes')" in breadcrumb
    assert "BreadcrumbItem('Object Storage', 'database')" in breadcrumb
    assert "BreadcrumbItem('Inventory')" in breadcrumb
    assert "BreadcrumbItem('Operations')" in breadcrumb
    assert "BreadcrumbItem('Analytics', 'chart-no-axes-combined')" in breadcrumb

    assert "BreadcrumbItem('Dashboards', 'layout-dashboard')" not in breadcrumb
    assert "BreadcrumbItem('Inventory', 'boxes')" not in breadcrumb


def test_capability_detail_navigation_replaces_retired_sidebar_submenus() -> None:
    model = (ROOT / 'app' / 'common' / 'workspace_navigation.py').read_text(encoding='utf-8')
    layout = (ROOT / 'app' / 'templates' / 'layouts' / 'app.html').read_text(encoding='utf-8')

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

    assert 'build_capability_navigation' in model
    assert '{% import "components/content_tabs.html" as content_tabs %}' in layout
    assert 'data-kaori-capability-navigation="{{ capability_navigation.key }}"' in layout
    assert 'content_tabs.render_links(' in layout
    assert "data_namespace='capability'" in layout
    assert 'nowrap=true' in layout

    assert "'Overview', 'layout-grid', 'inventory.overview'" in model
    assert "'Topology', 'waypoints', 'inventory.topology'" in model
    assert "'ConfigMaps'," in model
    assert "'Secrets'," in model
    assert "'TLS Certificates'," in model
    assert "'Resource Profiles'," in model
    assert "'Buckets & Containers'," in model
    assert "'Capacity & Usage'," in model


def test_navigation_context_is_preserved_without_becoming_navigation_identity() -> None:
    model = (ROOT / 'app' / 'common' / 'workspace_navigation.py').read_text(encoding='utf-8')
    presentation = (ROOT / 'app' / 'bootstrap' / 'presentation.py').read_text(encoding='utf-8')
    standard = (
        ROOT / 'docs' / 'design' / 'components' / 'DOMAIN_WORKSPACE_NAVIGATION.md'
    ).read_text(encoding='utf-8')

    assert "_WORKSPACE_CONTEXT_KEYS" in model
    assert "'kubernetes': ('cluster_id',)" in model
    assert "'object_storage': ('system_id',)" in model
    assert "'kubernetes_analytics': ('cluster_id', 'time_range')" in model
    assert "'object_storage_analytics': ('system_id', 'time_range')" in model
    assert "'kubernetes_operations': ('cluster_id', 'namespace')" in model
    assert '_preserved_context' in model
    assert 'build_workspace_navigation(request.endpoint, current_user, request.args)' in presentation
    assert 'build_capability_navigation(request.endpoint, current_user, request.args)' in presentation
    assert 'Filters that are meaningful only to one page remain page-local' in standard


def test_analytics_overview_does_not_duplicate_route_and_summary_tabsets() -> None:
    model = (ROOT / 'app' / 'common' / 'workspace_navigation.py').read_text(encoding='utf-8')
    overview = (
        ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'index.html'
    ).read_text(encoding='utf-8')

    assert "capability_key == 'kubernetes_analytics' and resolved_endpoint == 'analytics.overview'" in model
    assert "return None" in model.split(
        "capability_key == 'kubernetes_analytics' and resolved_endpoint == 'analytics.overview'", 1
    )[1].split('visible_views', 1)[0]

    assert "content_tabs.render_buttons('overview-content'" in overview
    assert 'View Resource Utilization' not in overview
    assert 'data-kaori-capability-navigation' not in overview
