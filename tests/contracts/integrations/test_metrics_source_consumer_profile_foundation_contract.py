from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_metrics_source_provider_full_validation_is_consumer_neutral() -> None:
    runtime = read('app/integrations/metrics/prometheus_http_runtime.py')
    core = read('app/integrations/metrics/prometheus_http_validation.py')
    compatibility = read('app/integrations/compatibility.py')
    compatibility_catalog = read('app/definitions/catalogs/integrations/compatibility.yaml')

    validate_body = runtime.split('def validate(self)', 1)[1].split('def audit_query_profile', 1)[0]
    assert 'validate_metrics_core' in validate_body
    assert 'PromQLProfileAuditor' not in validate_body
    assert 'kube_' not in core
    assert 'minio_' not in core
    assert "PROFILE_KEY = 'prometheus-http-core-v1'" in core
    assert 'integration_compatibility_document()' in compatibility
    assert 'query_profile: prometheus-http-core-v1' in compatibility_catalog


def test_consumer_validation_profiles_are_asset_scoped() -> None:
    profiles = read('app/integrations/metrics/binding_profiles.py')
    profile_catalog = read('app/definitions/catalogs/integrations/metrics_source.yaml')
    minio = read('app/integrations/minio/__init__.py')
    binding_validation = read('app/integrations/metrics/binding_validation.py')
    kubernetes_validator = read('app/integrations/metrics/binding_validators/kubernetes.py')
    object_storage_validator = read('app/integrations/metrics/binding_validators/object_storage.py')
    resolver = read('app/metrics/resolver.py')

    assert 'profile_key: kubernetes-metrics-v1' in profile_catalog
    assert 'profile_key: object-storage-metrics-v1' in profile_catalog
    assert "integration_provider_document('metrics_source')" in profiles
    assert "profile_key='minio-metrics-2024-v1'" not in minio
    assert 'register_binding_validation_profile' not in minio
    assert 'get_binding_validation_profile(instance.adapter_key, binding.asset_type)' in binding_validation
    assert 'get_binding_validator(instance.adapter_key, binding.asset_type)' in binding_validation
    assert 'binding.validation_evidence' in binding_validation
    assert '_validation_failure_evidence' in binding_validation
    assert "previous_payload.get('profile_key') == profile.profile_key" in binding_validation
    assert "'last_validation_attempt'" in binding_validation
    assert 'PromQLProfileAuditor(client).audit' not in binding_validation
    assert 'PromQLProfileAuditor(client).audit' in kubernetes_validator
    assert 'ObjectStorageMetricsProfileAuditor' in object_storage_validator
    assert '_VALIDATION_ADAPTERS' in object_storage_validator
    assert 'binding.validation_evidence or {}' in resolver


def test_binding_persists_profile_and_validation_evidence() -> None:
    model = read('app/models/integration.py')
    migration = read('migrations/versions/20260812_prometheus_consumer_validation_profiles.py')
    generalization = read('migrations/versions/20260817_metrics_source_generalization.py')

    assert 'validation_profile: Mapped[str | None]' in model
    assert 'validation_evidence: Mapped[dict | None]' in model
    assert "revision = '20260812_prom_consumer_profiles'" in migration
    assert "down_revision = '20260812_minio_object_storage'" in migration
    assert "SET readiness_status = 'validation_required'" in migration
    assert "SET query_profile = 'prometheus-core-v1'" in migration
    assert "SET query_profile = 'prometheus-http-core-v1'" in generalization
    assert "WHERE query_profile = 'prometheus-core-v1'" in generalization
    assert "SET validation_status = 'validation_required'" in migration


def test_metrics_source_ui_separates_provider_and_consumer_readiness() -> None:
    validation = read('app/templates/metrics/partials/_detail_validation_content.html')
    scope = read('app/templates/metrics/partials/_detail_scope.html')
    registry = read('app/templates/metrics/partials/_binding_registry.html')

    assert 'Metrics Source Full Validation' in validation
    assert 'Metrics Source Provider Readiness' in validation
    assert (
        'Full Validation owns core APIs; bindings own consumer evidence; Runtime Refresh owns live health.'
        in validation
    )
    assert 'Consumer Bindings' in scope
    assert 'Consumer Identity Boundary' in scope
    assert 'consumer_profile_label' in registry


def test_domain_route_does_not_depend_on_service_reexport() -> None:
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')

    assert 'from app.integrations.domain_service import (' in routes
    assert 'build_integration_domain_page' in routes
    assert 'from app.integrations.domain_service import build_integration_domain_page' not in service


def test_integration_docs_lock_provider_core_and_consumer_profile_boundary() -> None:
    kernel_readme = read('app/integrations/README.md')
    compatibility = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert 'Provider\n  → Compatibility Profile' in kernel_readme
    assert '→ Consumer Profile\n  → Binding Validation\n  → Consumer Eligibility' in kernel_readme
    assert '## Validation lifecycle' in compatibility
    assert '## Adding another metrics provider' in compatibility
    assert 'A missing Kubernetes metric may degrade one Kubernetes binding' in compatibility
    assert 'Provider Core Validation is product/version/API scoped.' in module_map
    assert 'Provider Core Validation is asynchronous and authoritative only for' in workspace_standard
    assert (
        'Consumer eligibility combines provider-owned execution capability evidence with asset-specific Binding Validation evidence.'
        in workspace_standard
    )
