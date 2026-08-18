from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_minimum_metrics_validation_follows_the_existing_modal_tab_pattern() -> None:
    source = read('app/templates/integrations/observability/metrics_source/partials/_minimum_validation_metrics.html')
    configuration = read('app/templates/integrations/observability/metrics_source/partials/_detail_configuration.html')
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )

    assert 'Minimum Metrics Validation Example' in source
    assert 'Open Metrics Examples' in source
    assert 'components/workspace_tabs.html' in source
    assert "('identity', 'Prometheus / Thanos Identity', 'fingerprint')" in source
    assert "('filesystem', 'Node Filesystem Relabel', 'hard-drive')" in source
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert 'x-teleport="body"' in source
    assert 'externalLabels:' in source
    assert 'targetLabel: cluster' in source
    assert 'replacement: k8s-production' in source
    assert 'cluster: k8s-production' in source
    assert 'targetLabel: node' in source
    assert '__meta_kubernetes_pod_node_name' in source
    assert '_minimum_validation_metrics.html' in configuration
    assert '_minimum_validation_metrics.html' not in validation


def test_binding_validation_enforces_cluster_source_identity_and_node_filesystem_identity() -> None:
    validator = read('app/integrations/observability/metrics_source/binding_validators/kubernetes.py')
    feature_contracts = read('app/integrations/observability/metrics_source/query_profiles/feature_contracts.py')
    queries = read('app/integrations/observability/metrics_source/query_profiles/kubernetes_v1.py')

    assert "matcher.label == 'cluster'" in validator
    assert 'client.label_values(cluster_matcher.label)' in validator
    assert 'query-visible target label' in validator
    assert "provider_key == 'thanos'" in validator
    assert "required_labels=('node',)" in feature_contracts
    assert 'count by (node, mountpoint)' in feature_contracts
    assert "('node_filesystem_size_bytes', ('node', 'mountpoint'))" in queries
    assert "('node_filesystem_avail_bytes', ('node', 'mountpoint'))" in queries


def test_consumer_missing_details_are_owned_by_validation_registry_not_provider_readiness() -> None:
    presentation = read('app/integrations/observability/metrics_source/application/presentation.py')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_capability_registry.html')
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    readiness = read('app/templates/integrations/components/_capability_readiness.html')

    assert 'consumer_validation_gap_rows = _consumer_validation_gap_rows' in presentation
    assert "'contract_scope': 'consumer'" in presentation
    assert 'Consumer Contract Evidence' in registry
    assert 'Binding Validation owns source identity, required metric labels, filesystem pairing' in registry
    assert 'consumer_validation_summary.gap_count' in validation
    assert 'missing_labels' not in readiness
    assert 'node_filesystem_size_bytes' not in readiness
    assert 'cluster source label' not in readiness.lower()
