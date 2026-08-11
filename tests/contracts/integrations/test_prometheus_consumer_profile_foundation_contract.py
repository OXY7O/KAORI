from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_prometheus_provider_full_validation_is_consumer_neutral() -> None:
    runtime = read('app/integrations/prometheus/runtime.py')
    core = read('app/integrations/prometheus/core_validation.py')
    compatibility = read('app/integrations/compatibility.py')

    validate_body = runtime.split('def validate(self)', 1)[1].split('def audit_query_profile', 1)[0]
    assert 'validate_prometheus_core' in validate_body
    assert 'PromQLProfileAuditor' not in validate_body
    assert 'kube_' not in core
    assert 'minio_' not in core
    assert "PROFILE_KEY = 'prometheus-core-v1'" in core
    assert 'prometheus-core-v1' in compatibility


def test_consumer_validation_profiles_are_asset_scoped() -> None:
    profiles = read('app/integrations/prometheus/binding_profiles.py')
    minio = read('app/integrations/minio/__init__.py')
    binding_validation = read('app/integrations/prometheus/binding_validation.py')
    resolver = read('app/prometheus/resolver.py')

    assert "profile_key='kubernetes-metrics-v1'" in profiles
    assert "profile_key='minio-metrics-2024-v1'" in minio
    assert 'get_binding_validation_profile(binding.asset_type)' in binding_validation
    assert 'binding.validation_evidence' in binding_validation
    assert 'PromQLProfileAuditor(client).audit' in binding_validation
    assert 'binding.validation_evidence or {}' in resolver


def test_binding_persists_profile_and_validation_evidence() -> None:
    model = read('app/models/integration.py')
    migration = read('migrations/versions/20260812_prometheus_consumer_validation_profiles.py')

    assert 'validation_profile: Mapped[str | None]' in model
    assert 'validation_evidence: Mapped[dict | None]' in model
    assert "revision = '20260812_prom_consumer_profiles'" in migration
    assert "down_revision = '20260812_minio_object_storage'" in migration
    assert "SET readiness_status = 'validation_required'" in migration
    assert "SET query_profile = 'prometheus-core-v1'" in migration
    assert "SET validation_status = 'validation_required'" in migration


def test_prometheus_ui_separates_provider_and_consumer_readiness() -> None:
    validation = read('app/templates/prometheus/partials/_detail_validation_content.html')
    scope = read('app/templates/prometheus/partials/_detail_scope.html')

    assert 'Prometheus Core Validation' in validation
    assert 'Prometheus Provider Readiness' in validation
    assert 'Consumer Validation Boundary' in validation
    assert 'Consumer Bindings' in scope
    assert 'consumer_profile_label' in scope


def test_domain_route_does_not_depend_on_service_reexport() -> None:
    routes = read('app/integrations/routes.py')
    service = read('app/integrations/service.py')

    assert 'from app.integrations.domain_service import build_integration_domain_page' in routes
    assert 'from app.integrations.domain_service import build_integration_domain_page' not in service
