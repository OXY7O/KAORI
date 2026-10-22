"""Kubernetes Admin HTMX policy mutations reconcile every Overview metric from server state."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_administration_mutations_refresh_hero_overview_and_posture():
    route = (ROOT / 'app/platform_operations/kubernetes/secret_reveal/routes.py').read_text()
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
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
        if fragment.startswith('kubernetes-admin-overview-metric-'):
            assert 'id="kubernetes-admin-overview-metric-{{ loop.index }}"' in overview
        else:
            assert 'id="' + fragment + '"' in (page + overview)
        assert 'id="' + fragment + '"' in partial
    assert partial.count('hx-swap-oob="innerHTML"') == 9


def test_admin_overview_tab_navigation_preserves_current_url_parameters():
    page = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    assert "setTab('secret-reveal')" in page
    assert 'history.replaceState(null' not in page



def test_kubernetes_admin_operational_hierarchy_keeps_authoritative_summary() -> None:
    page = (ROOT / 'app/templates/platform_operations/kubernetes/index.html').read_text()
    overview = (ROOT / 'app/templates/platform_operations/kubernetes/_overview_workspace.html').read_text()
    config = (ROOT / 'app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html').read_text()
    cluster = (ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html').read_text()

    assert 'Kubernetes Administration</h1>' in page
    assert 'components/page_hero.html' in page
    assert 'framed_workspace_tabs.render(' in page
    assert 'kubernetes:load-secret-reveal from:window once' in page
    assert 'kubernetes-administration-overview-title' not in page
    assert 'Administration Readiness' in overview
    assert 'Configuration Checks' in overview
    assert 'Configure Secret Reveal' in overview
    for obsolete in ('Administration Capability Catalog', 'Recommended Administration Domains', 'Recommended Roadmap'):
        assert obsolete not in overview + page
    assert 'administration_status_detail' in overview
    assert 'Secret Reveal Configuration' in config
    assert 'Deployment-managed. Read-only here.' in config
    assert 'do not prove live access' in config
    for marker in (
        'secret-reveal-protected-cluster-count',
        'secret-reveal-enabled-namespace-count',
        'secret-reveal-selected-cluster-posture',
        'secret-reveal-selected-cluster-summary',
    ):
        assert f'id="{marker}"' in config
        assert f'id="{marker}"' in cluster
    assert 'hx-swap-oob="outerHTML"' in cluster
    assert 'Selected Cluster Readiness' in config
    assert 'Selected Cluster Readiness' in cluster
    assert 'platform_operations/kubernetes/secret_reveal/_cluster_workspace.html' in config
