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


def test_sidebar_standard_is_registered_as_authoritative_design_document() -> None:
    readme = (ROOT / 'docs' / 'design' / 'README.md').read_text(encoding='utf-8')
    design_system = (ROOT / 'docs' / 'design' / 'DESIGN_SYSTEM.md').read_text(encoding='utf-8')
    standard = (ROOT / 'docs' / 'design' / 'components' / 'SIDEBAR_NAVIGATION.md').read_text(encoding='utf-8')

    assert 'locked application-shell navigation contract' in readme
    assert 'locked v1.5 sidebar hierarchy' in design_system
    assert 'The earlier 12/11 px markdown baseline' in standard
    assert 'KAORI Sidebar Navigation Standard v1.5' in standard
    assert 'dark mode keeps the active Violet surface without a separate left-edge accent' in standard
    assert '## Navigation Naming Contract' in standard
    assert 'Section provides domain context' in standard
    assert '15/13 px visual-guide draft' in standard



def test_navigation_content_hierarchy_matches_design_system_v2_contract() -> None:
    sidebar = (ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'sidebar.html').read_text(encoding='utf-8')
    analytics_menu = (
        ROOT / 'app' / 'templates' / 'components' / 'navigation' / 'analytics_menu.html'
    ).read_text(encoding='utf-8')
    breadcrumb = (ROOT / 'app' / 'common' / 'navigation.py').read_text(encoding='utf-8')
    kubernetes_overview = (
        ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')
    object_storage_pages = (
        ROOT / 'app' / 'storage' / 'object_storage' / 'analytics' / 'pages.py'
    ).read_text(encoding='utf-8')

    assert '>Analytics</div>' in sidebar
    assert sidebar.index('>Storage</div>') < sidebar.index('>Analytics</div>') < sidebar.index('>Insights</div>')
    assert '>Kubernetes</span>' in analytics_menu
    assert '>Object Storage</span>' in analytics_menu
    assert '>Kubernetes Analytics</span>' not in analytics_menu
    assert '>Object Storage Analytics</span>' not in analytics_menu

    assert "BreadcrumbItem('Analytics', 'chart-no-axes-combined')" in breadcrumb
    assert "BreadcrumbItem('Kubernetes', 'bar-chart-3')" in breadcrumb
    assert "BreadcrumbItem('Object Storage', 'database-zap')" in breadcrumb
    assert "BreadcrumbItem('Object Storage Inventory', 'database')" not in breadcrumb

    assert '>Overview</h1>' in kubernetes_overview
    assert "'Overview'," in object_storage_pages
    assert "'Capacity & Usage'," in object_storage_pages
    assert "'Performance'," in object_storage_pages
    assert "'Object Storage Capacity & Usage'," not in object_storage_pages
    assert "'Object Storage Performance'," not in object_storage_pages

    kubernetes_titles = {
        'utilization/routes.py': ("'title': 'Utilization'", "'title': 'Resource Utilization'"),
        'capacity/routes.py': ("'title': 'Capacity'", "'title': 'Capacity Analysis'"),
        'storage/routes.py': ("'title': 'Storage'", "'title': 'Storage Analysis'"),
        'workload/routes.py': ("'title': 'Workloads'", "'title': 'Workload Analysis'"),
        'forecast/routes.py': ("'title': 'Forecast'", "'title': 'Resource Forecast'"),
    }
    analytics_root = ROOT / 'app' / 'kubernetes' / 'analytics'
    for relative, (expected, obsolete) in kubernetes_titles.items():
        source = (analytics_root / relative).read_text(encoding='utf-8')
        assert expected in source
        assert obsolete not in source
