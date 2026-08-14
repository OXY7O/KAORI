from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_cluster_blocked_hero_preserves_dashboard_semantics() -> None:
    shared = _read('app/templates/components/cluster/_hero_blocked_context.html')

    assert "page_hero.context_header(blocked_scope, blocked_title, 'lock-keyhole')" in shared
    assert "page_hero.context_metric('boxes', 'Connected Clusters', '0', 'No Kubernetes connection available')" in shared
    assert "page_hero.context_metric('circle-dot-dashed', blocked_state_label, 'Blocked', 'Cluster access is required'" in shared
    assert "cluster_blocked_state_label|default('Workspace State')" in shared
    assert "page_hero.context_info('triangle-alert', blocked_info)" in shared


def test_dashboard_operations_and_governance_share_the_blocked_hero_component() -> None:
    expected = {
        'app/templates/dashboards/kubernetes/partials/_hero.html': 'Dashboard Readiness',
        'app/templates/kubernetes_operations/cluster_required.html': 'Operations Readiness',
        'app/templates/governance/overview/index.html': 'Governance Readiness',
        'app/templates/governance/tls_certificates/partials/_hero.html': 'Governance Readiness',
    }
    for relative, readiness_label in expected.items():
        source = _read(relative)
        assert "components/cluster/_hero_blocked_context.html" in source, relative
        assert readiness_label in source, relative
        assert 'Cluster Setup Required' in source, relative


def test_every_inventory_hero_uses_the_shared_blocked_context() -> None:
    resources = (
        'overview',
        'nodes',
        'namespaces',
        'configuration',
        'workloads',
        'pods',
        'services',
        'ingresses',
        'storage',
        'topology',
    )
    for resource in resources:
        source = _read(f'app/templates/inventory/kubernetes/{resource}/partials/_hero.html')
        assert '{% if cluster_onboarding.is_blocked %}' in source, resource
        assert 'Inventory Readiness' in source, resource
        assert "components/cluster/_hero_blocked_context.html" in source, resource
        assert '{% else %}' in source, resource


def test_tls_governance_does_not_present_zero_inventory_as_blocked_evidence() -> None:
    source = _read('app/templates/governance/tls_certificates/partials/_hero.html')
    blocked_branch = source.split('{% if cluster_onboarding.is_blocked %}', 1)[1].split('{% else %}', 1)[0]

    assert '0 Clusters Connected' not in blocked_branch
    assert 'Cluster Setup Required' in blocked_branch


def test_dashboard_keeps_its_existing_blocked_state_label() -> None:
    source = _read('app/templates/dashboards/kubernetes/partials/_hero.html')
    assert 'cluster_blocked_state_label = "Dashboard State"' in source

def test_dashboard_blocked_hero_does_not_double_wrap_the_shared_context_panel() -> None:
    source = _read('app/templates/dashboards/kubernetes/partials/_hero.html')
    blocked_branch = source.split('{% if cluster_onboarding.is_blocked %}', 1)[1].split('{% else %}', 1)[0]
    normal_branch = source.split('{% else %}', 1)[1].split('{% endif %}', 1)[0]

    assert 'page_hero.context_panel_classes()' not in blocked_branch
    assert "components/cluster/_hero_blocked_context.html" in blocked_branch
    assert 'page_hero.context_panel_classes()' in normal_branch

