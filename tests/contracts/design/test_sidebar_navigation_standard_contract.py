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

    assert 'locked application-shell navigation contract' in readme
    assert 'DOMAIN_WORKSPACE_NAVIGATION.md' in readme
    assert 'locked v2 global Section → Workspace' in design_system
    assert 'KAORI Sidebar Navigation Standard v2.0' in sidebar_standard
    assert 'A third level in the global sidebar is prohibited.' in sidebar_standard
    assert 'KAORI Domain Workspace Navigation Standard v1.0' in workspace_standard
    assert 'workspace_tabs.render_navigation()' in workspace_standard


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
