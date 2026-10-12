"""Kubernetes Admin HTMX policy mutations reconcile every Overview metric from server state."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_administration_mutations_refresh_hero_overview_and_posture():
    route = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    partial = (ROOT / 'app/templates/platform_operations/kubernetes/_summary_oob.html').read_text()
    assert 'build_kubernetes_administration_summary()' in route
    assert 'workspace_html + summary_html + feedback_html' in route
    for fragment in (
        'kubernetes-admin-hero-registered',
        'kubernetes-admin-hero-configured',
        'kubernetes-admin-hero-protected',
        'kubernetes-admin-context-ready',
        'kubernetes-admin-context-status',
        'kubernetes-admin-overview-status',
        'kubernetes-admin-overview-metric-2',
        'kubernetes-admin-overview-metric-3',
        'kubernetes-admin-overview-metric-4',
    ):
        assert 'id="' + fragment + '"' in page
        assert 'id="' + fragment + '"' in partial
    assert partial.count('hx-swap-oob="innerHTML"') == 9


def test_admin_overview_tab_navigation_preserves_current_url_parameters():
    page = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    assert 'setTab(\'secret-reveal\')' in page
    assert 'history.replaceState(null' not in page
