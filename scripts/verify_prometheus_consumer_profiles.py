#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    routes = read('app/integrations/routes.py')
    compatibility = read('app/integrations/compatibility.py')
    runtime = read('app/integrations/prometheus/runtime.py')
    core = read('app/integrations/prometheus/core_validation.py')
    profiles = read('app/integrations/prometheus/binding_profiles.py')
    minio = read('app/integrations/minio/__init__.py')
    binding_validation = read('app/integrations/prometheus/binding_validation.py')
    resolver = read('app/prometheus/resolver.py')
    model = read('app/models/integration.py')
    migration = read('migrations/versions/20260812_prometheus_consumer_validation_profiles.py')
    validation_template = read('app/templates/prometheus/partials/_detail_validation_content.html')
    kernel_readme = read('app/integrations/README.md')
    compatibility_doc = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert 'from app.integrations.domain_service import build_integration_domain_page' in routes
    assert 'prometheus-core-v1' in compatibility

    validate_body = runtime.split('def validate(self)', 1)[1].split('def audit_query_profile', 1)[0]
    assert 'validate_prometheus_core' in validate_body
    assert 'PromQLProfileAuditor' not in validate_body
    assert 'Kubernetes Analytics' not in validate_body

    assert 'kube_' not in core
    assert 'minio_' not in core
    assert "PROFILE_KEY = 'prometheus-core-v1'" in core

    assert "profile_key='kubernetes-metrics-v1'" in profiles
    assert "profile_key='minio-metrics-2024-v1'" in minio
    assert 'PromQLProfileAuditor(client).audit' in binding_validation
    assert 'binding.validation_evidence' in binding_validation

    assert 'validation_profile:' in model
    assert 'validation_evidence:' in model
    assert 'binding.validation_evidence or {}' in resolver
    assert 'instance.capabilities or {}' not in resolver.split('def _evaluate_binding', 1)[1].split('def _operational_rank', 1)[0]

    assert "revision = '20260812_prom_consumer_profiles'" in migration
    assert "down_revision = '20260812_minio_object_storage'" in migration
    assert "SET readiness_status = 'validation_required'" in migration
    assert "SET query_profile = 'prometheus-core-v1'" in migration
    assert "SET validation_status = 'validation_required'" in migration

    assert 'Prometheus Core Validation' in validation_template
    assert 'Consumer Validation Boundary' in validation_template
    assert 'Kubernetes, MinIO, and other metric contracts are validated through their asset-scoped bindings.' in validation_template

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
    assert '## Canonical provider-to-consumer contract' in compatibility_doc
    assert 'Provider Core Validation is product/version/API scoped.' in module_map
    assert 'Provider Core Validation is asynchronous and authoritative only for' in workspace_standard
    assert 'Consumer eligibility is derived from Binding Validation evidence' in workspace_standard

    print('PASS — Prometheus provider readiness is consumer-neutral and consumer metrics are binding-scoped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
