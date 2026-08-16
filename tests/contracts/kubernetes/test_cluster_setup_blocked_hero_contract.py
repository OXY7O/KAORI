from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_cluster_blocked_hero_preserves_dashboard_semantics() -> None:
    shared = _read('app/templates/components/cluster/_hero_blocked_context.html')

    assert "page_hero.context_header(blocked_scope, blocked_title, 'lock-keyhole')" in shared
    assert (
        "page_hero.context_metric('boxes', 'Connected Clusters', '0', 'No Kubernetes connection available')" in shared
    )
    assert (
        "page_hero.context_metric('circle-dot-dashed', blocked_state_label, 'Blocked', 'Cluster access is required'"
        in shared
    )
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
        assert 'components/cluster/_hero_blocked_context.html' in source, relative
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
        assert 'components/cluster/_hero_blocked_context.html' in source, resource
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
    assert 'components/cluster/_hero_blocked_context.html' in blocked_branch
    assert 'page_hero.context_panel_classes()' in normal_branch


def test_inventory_blocked_hero_metadata_does_not_present_zero_counts_as_evidence() -> None:
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
        metadata = source.split('page_hero.metadata_row_classes()', 1)[1].split('</div>', 1)[0]
        assert 'cluster_onboarding.is_blocked' in metadata, resource
        assert 'Committed Inventory' in metadata, resource
        assert 'Cluster Setup Required' in metadata, resource


def test_tls_governance_cluster_setup_precedes_schema_readiness() -> None:
    source = _read('app/templates/governance/tls_certificates/partials/_page_content.html')
    cluster_blocker = source.index('{% if cluster_onboarding.is_blocked %}')
    schema_blocker = source.index('{% elif not payload.schema_readiness.ready %}')
    workspace = source.index('partials/_page_workspace.html')

    assert cluster_blocker < schema_blocker < workspace


def test_governance_and_operations_blocked_copy_remains_domain_specific() -> None:
    governance = _read('app/templates/governance/overview/index.html')
    tls_hero = _read('app/templates/governance/tls_certificates/partials/_hero.html')
    tls_detail = _read('app/templates/governance/tls_certificates/detail.html')
    operations = _read('app/templates/kubernetes_operations/cluster_required.html')

    assert 'Governance Controls' in governance
    assert "meta_label('server-cog', 'Kubernetes Operations')" not in governance
    assert (
        'Review certificate validity, host coverage, issuer posture, renewal windows, and rotation readiness.'
        in tls_hero
    )
    assert (
        'Review certificate validity, host coverage, issuer details, and committed collection evidence.' in tls_detail
    )
    assert '{{ requested_page_title }}' in operations
    assert '{{ requested_page_description }}' in operations
    assert '>Kubernetes Cluster Setup Required</h1>' not in operations


def test_setup_blockers_preserve_page_identity_from_kubernetes_to_object_storage() -> None:
    dashboard = _read('app/templates/dashboards/kubernetes/partials/_hero.html')
    k8s_analytics = _read('app/templates/analytics/kubernetes/materialization/blocked.html')
    governance = _read('app/templates/governance/overview/index.html')
    tls_governance = _read('app/templates/governance/tls_certificates/partials/_hero.html')
    operations = _read('app/templates/kubernetes_operations/cluster_required.html')
    object_storage_overview = _read('app/templates/inventory/object_storage/overview/partials/_hero.html')
    object_storage_systems = _read('app/templates/inventory/object_storage/systems/partials/_hero.html')
    object_storage_buckets = _read('app/templates/inventory/object_storage/buckets/partials/_hero.html')
    object_storage_analytics = _read('app/templates/analytics/object_storage/partials/_hero.html')

    assert 'Kubernetes Operations Dashboard' in dashboard
    assert '{{ materialization_title }}' in k8s_analytics
    assert 'Kubernetes Governance Workspace' in governance
    assert 'TLS Certificate Governance' in tls_governance
    assert '{{ requested_page_title }}' in operations
    assert 'Object Storage Overview' in object_storage_overview
    assert 'Object Storage Systems' in object_storage_systems
    assert 'Buckets &amp; Containers' in object_storage_buckets
    assert '{{ page.title }}' in object_storage_analytics

    for source in (
        dashboard,
        k8s_analytics,
        governance,
        tls_governance,
        operations,
        object_storage_overview,
        object_storage_systems,
        object_storage_buckets,
        object_storage_analytics,
    ):
        h1_lines = [line for line in source.splitlines() if '<h1' in line or 'page_hero.title_classes()' in line]
        assert not any('Setup Required' in line for line in h1_lines)
