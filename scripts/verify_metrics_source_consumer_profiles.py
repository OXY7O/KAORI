#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    routes = read('app/integrations/routes.py')
    compatibility = read('app/integrations/compatibility.py')
    compatibility_catalog = read('app/definitions/catalogs/integrations/compatibility.yaml')
    runtime = read('app/integrations/observability/metrics_source/adapters/prometheus_http/runtime.py')
    core = read('app/integrations/observability/metrics_source/adapters/prometheus_http/validation.py')
    profiles = read('app/integrations/observability/metrics_source/binding_profiles.py')
    profile_catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    minio = read('app/integrations/storage/object_storage/providers/minio/__init__.py')
    binding_validation = read('app/integrations/observability/metrics_source/binding_validation.py')
    kubernetes_validator = read('app/integrations/observability/metrics_source/binding_validators/kubernetes.py')
    object_storage_validator = read(
        'app/integrations/observability/metrics_source/binding_validators/object_storage.py'
    )
    resolver = read('app/integrations/observability/metrics_source/application/resolver.py')
    model = read('app/models/integration.py')
    migration = read('migrations/versions/20260812_prometheus_consumer_validation_profiles.py')
    generalization = read('migrations/versions/20260817_metrics_source_generalization.py')
    validation_template = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )
    readiness_template = read('app/templates/integrations/components/_readiness_explanation.html')
    binding_template = read('app/templates/integrations/observability/metrics_source/partials/_binding_registry.html')
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    consumer_assets = read('app/integrations/consumer_assets.py')
    taxonomy_catalog = read('app/definitions/catalogs/integrations/taxonomy.yaml')
    kernel_readme = read('app/integrations/README.md')
    compatibility_doc = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    promql_audit = read('app/integrations/observability/metrics_source/query_profiles/audit.py')
    feature_contracts = read(
        'app/integrations/observability/metrics_source/query_profiles/feature_contracts.py'
    )
    forecast_profile = read('app/integrations/observability/metrics_source/query_profiles/forecast_v1.py')
    promql_doc = read('docs/PROMQL_QUERY_PROFILES.md')

    assert 'from app.integrations.domain_service import (' in routes
    assert 'build_integration_domain_page,' in routes
    assert 'integration_compatibility_document()' in compatibility
    assert 'query_profile: prometheus-http-core-v1' in compatibility_catalog

    validate_body = runtime.split('def validate(self)', 1)[1].split('def audit_query_profile', 1)[0]
    assert 'validate_metrics_core' in validate_body
    assert 'PromQLProfileAuditor' not in validate_body
    assert 'Kubernetes Analytics' not in validate_body

    assert 'kube_' not in core
    assert 'minio_' not in core
    assert "PROFILE_KEY = 'prometheus-http-core-v1'" in core

    assert "integration_provider_document('metrics_source')" in profiles
    assert 'profile_key: kubernetes-metrics-v1' in profile_catalog
    assert 'profile_key: object-storage-metrics-v1' in profile_catalog
    assert "profile_key='minio-metrics-2024-v1'" not in minio
    assert 'register_binding_validation_profile' not in minio
    assert 'get_binding_validator(instance.adapter_key, binding.asset_type)' in binding_validation
    assert 'PromQLProfileAuditor(client).audit' in kubernetes_validator
    assert 'ObjectStorageMetricsProfileAuditor' in object_storage_validator
    assert '_VALIDATION_ADAPTERS' in object_storage_validator
    assert 'binding.validation_evidence' in binding_validation

    assert 'validation_profile:' in model
    assert 'validation_evidence:' in model
    assert 'binding.validation_evidence or {}' in resolver
    assert 'instance.capabilities or {}' in resolver
    assert 'def _available_technical_capabilities' in resolver
    assert 'observed = _available_technical_capabilities(binding, instance)' in resolver

    assert "revision = '20260812_prom_consumer_profiles'" in migration
    assert "down_revision = '20260812_minio_object_storage'" in migration
    assert "SET readiness_status = 'validation_required'" in migration
    assert "SET query_profile = 'prometheus-core-v1'" in migration
    assert "SET query_profile = 'prometheus-http-core-v1'" in generalization
    assert "WHERE query_profile = 'prometheus-core-v1'" in generalization
    assert "SET validation_status = 'validation_required'" in migration

    assert 'Metrics Source Full Validation' in validation_template
    assert 'integrations/components/_readiness_explanation.html' in validation_template
    assert 'data-kaori-consumer-readiness-boundary' in readiness_template
    assert 'Consumer Binding Registry' in binding_template
    assert 'data-kaori-observability-binding-modal' in binding_modal
    assert 'integration_taxonomy_document()' in consumer_assets
    assert 'asset_type: kubernetes_cluster' in taxonomy_catalog
    assert 'asset_type: object_storage_system' in taxonomy_catalog
    assert 'Consumer contracts stay in Bindings & Consumers.' in validation_template
    assert 'consumer capabilities stay outside this registry' in validation_template
    assert 'View More' in binding_template
    assert 'data-kaori-binding-view-more' in binding_template
    assert 'data-kaori-binding-actions' in binding_template
    assert '_binding_validation_result.html' in binding_template

    assert forecast_profile.count("required_history='90d'") >= 13
    assert 'retention = self.validate_retention(retention_horizons(definitions))' in promql_audit
    assert 'long_term_history_assessment(retention)' in promql_audit
    assert 'retention=retention' in promql_audit
    assert 'required_histories.add(definition.required_history)' in feature_contracts
    assert 'technical_history_check(required_history, retention)' in feature_contracts
    assert 'shared query contract is `prometheus-http-core-v1`' in promql_doc
    assert 'does not ask the operator to choose a Prometheus "HTTP v2/v3" profile' in promql_doc

    canonical_flow = (
        'Provider\n'
        '  → Compatibility Profile\n'
        '  → Provider Capability Set\n'
        '  → Core Validation\n'
        '  → Provider Ready\n'
        '  → Asset Binding\n'
        '  → Consumer Profile\n'
        '  → Binding Validation\n'
        '  → Consumer Eligibility'
    )
    assert canonical_flow in kernel_readme
    assert '## Validation lifecycle' in compatibility_doc
    assert '## Adding another metrics provider' in compatibility_doc
    assert 'Provider Core Validation is product/version/API scoped.' in module_map
    assert 'Provider Core Validation is asynchronous and authoritative only for' in workspace_standard
    assert 'Consumer eligibility combines provider-owned execution capability evidence' in workspace_standard

    print('PASS — Metrics Source provider readiness is adapter-driven and consumer metrics are binding-scoped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
