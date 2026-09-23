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
    shared_configuration = read('app/templates/integrations/components/_provider_configuration_contract.html')

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
    assert (
        'setup_reference_template="integrations/observability/metrics_source/partials/_minimum_validation_metrics.html"'
        in configuration
    )
    assert '<div class="mt-4">' not in configuration
    assert 'setup_reference_template=""' in shared_configuration
    assert '{% include setup_reference_template %}' in shared_configuration
    assert shared_configuration.index('operational_context.render') < shared_configuration.index(
        '{% include setup_reference_template %}'
    )
    assert shared_configuration.index('{% include setup_reference_template %}') < shared_configuration.index('<footer')
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


def test_provider_capability_registry_stays_core_only_and_binding_results_stay_with_bindings() -> None:
    presentation = read('app/integrations/observability/metrics_source/application/presentation.py')
    registry = read('app/templates/integrations/observability/metrics_source/partials/_capability_registry.html')
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    binding_registry = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    binding_result = read('app/templates/integrations/components/_binding_validation_result.html')
    scope = read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html')
    readiness = read('app/templates/integrations/components/_capability_readiness.html')

    assert 'capability_rows = provider_capability_rows' in presentation
    assert '_consumer_validation_rows' not in presentation
    assert "'contract_scope': 'provider'" in presentation
    assert 'Provider Core Capability' in registry
    assert 'Consumer Contract Evidence' not in registry
    assert 'Consumer contracts stay in Bindings & Consumers.' in validation
    assert 'consumer capabilities stay outside this registry' in validation
    assert '_binding_validation_result.html' in binding_registry
    assert 'View More' in binding_registry
    assert 'data-kaori-binding-view-more' in binding_registry
    assert 'data-kaori-binding-actions' in binding_registry
    assert 'Binding Validation Result' in binding_result
    assert 'Consumer Capability Evidence' in binding_result
    assert '90d History Availability' not in validation
    assert 'Missing technical capability:' not in scope
    assert 'Binding coverage missing:' not in scope
    assert 'missing_labels' not in readiness
    assert 'node_filesystem_size_bytes' not in readiness
    assert 'cluster source label' not in readiness.lower()


def test_forecast_binding_validation_uses_declared_90_day_history_independent_of_http_major() -> None:
    audit = read('app/integrations/observability/metrics_source/query_profiles/audit.py')
    feature_contracts = read('app/integrations/observability/metrics_source/query_profiles/feature_contracts.py')
    forecast = read('app/integrations/observability/metrics_source/query_profiles/forecast_v1.py')
    compatibility = read('app/definitions/catalogs/integrations/compatibility.yaml')
    provider_contract = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    retention = read('app/integrations/observability/metrics_source/query_profiles/retention.py')
    docs = read('docs/PROMQL_QUERY_PROFILES.md')

    assert forecast.count("required_history='90d'") >= 13
    assert 'retention = self.validate_retention(retention_horizons(definitions))' in audit
    assert 'long_term_history_assessment(retention)' in audit
    assert "horizon: str = '90d'" in retention
    assert "'label': f'{horizon} History Availability'" in retention
    assert 'retention=retention' in audit
    assert 'required_histories.add(definition.required_history)' in feature_contracts
    assert 'technical_history_check(required_history, retention)' in feature_contracts
    # Product versions are qualification rows; the runtime query identity stays on one shared HTTP core contract.
    assert 'key: prometheus-http-core-v1' in compatibility
    assert 'key: prometheus-extended' in compatibility
    assert 'key: prometheus-current' in compatibility
    assert 'contract_profile: prometheus-http-core-v1' in compatibility
    assert 'key: thanos-extended' in compatibility
    assert 'key: thanos-current' in compatibility
    assert 'thanos-query-v0-39' not in compatibility
    assert 'thanos-query-v0-42' not in compatibility
    assert 'version_detection_mode: automatic' in provider_contract
    assert 'selection_mode: automatic_detected_version' in compatibility
    assert 'version_source: prometheus_buildinfo' in compatibility
    assert 'version_source: thanos_buildinfo' in compatibility
    thanos = provider_contract.split('- key: thanos', 1)[1].split('compatibility_profiles:', 1)[0]
    assert 'compatibility_profile_options: []' in thanos
    assert 'Prometheus HTTP API v2' not in thanos
    assert 'Prometheus HTTP API v3' not in thanos
    assert compatibility.count('query_profile: prometheus-http-core-v1') == 1
    assert 'shared query contract is `prometheus-http-core-v1`' in docs
    assert 'does not ask the operator to choose a Prometheus "HTTP v2/v3" profile' in docs
    assert "required_history='90d'" in docs
