#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    registration = read('app/integrations/alertmanager/__init__.py')
    capabilities = read('app/integrations/alertmanager/capabilities.py')
    requirements = read('app/integrations/alertmanager/requirements.py')
    validation = read('app/integrations/alertmanager/validation.py')
    profiles = read('app/integrations/alertmanager/binding_profiles.py')
    binding_validation = read('app/integrations/alertmanager/binding_validation.py')
    resolver = read('app/alertmanager/resolver.py')
    forms = read('app/alertmanager/forms.py')
    minio_service = read('app/minio/service.py')
    validation_template = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    scope_template = read('app/templates/alertmanager/partials/_detail_scope.html')
    minio_index = read('app/templates/minio/index.html')
    provider_tabs = read('app/templates/components/integration_workspace_tabs.html')
    minio_detail = read('app/templates/minio/instance_detail.html')
    alertmanager_readme = read('app/integrations/alertmanager/README.md')
    compatibility_doc = read('docs/INTEGRATION_COMPATIBILITY.md')
    module_map = read('docs/architecture/integration-module-map.md')
    workspace_standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')

    assert 'CORE_CAPABILITY_KEYS' in registration
    assert "CORE_CAPABILITY_KEYS = ('status_v2', 'alerts_v2', 'silences_v2')" in capabilities
    assert 'Kubernetes' not in requirements
    assert 'MinIO' not in requirements
    assert 'discover_payload_capabilities' not in validation

    assert "profile_key='kubernetes-alerts-v1'" in profiles
    assert "profile_key='minio-alerts-v1'" in profiles
    assert "asset_type='object_storage_system'" in profiles
    assert 'discover_payload_capabilities' in binding_validation
    assert 'binding.validation_evidence' in binding_validation
    assert 'binding.validation_profile' in binding_validation

    evaluator = resolver.split('def _evaluate_binding', 1)[1].split('def _operational_rank', 1)[0]
    assert 'binding.validation_evidence or {}' in evaluator
    assert 'instance.capabilities or {}' not in evaluator

    assert "'object_storage_system'" in forms
    assert 'object_storage_scope_key' in forms
    assert "create_source_binding(\n        'alertmanager'" in minio_service
    assert 'asset_type=OBJECT_STORAGE_SYSTEM_SCOPE' in minio_service

    assert 'Alertmanager Core Validation' in validation_template
    assert 'Consumer Validation Boundary' in validation_template
    assert 'Consumer Binding Registry' in scope_template
    assert 'Consumer Profile' in scope_template

    assert 'MinIO Integrations' in minio_index
    assert 'Register Connection' in minio_index
    assert 'Integration Coverage' in provider_tabs
    assert 'Connection Registry' in provider_tabs
    assert 'Core Validation' in minio_detail
    assert 'Bindings & Consumers' in minio_detail

    assert 'kubernetes-alerts-v1' in alertmanager_readme
    assert 'minio-alerts-v1' in alertmanager_readme
    assert 'Consumer alert contracts are binding-scoped.' in compatibility_doc
    assert 'Alertmanager consumer-profile boundary' in module_map
    assert 'Alertmanager provider validation is consumer-neutral' in workspace_standard
    assert 'MinIO uses the same provider workspace hierarchy as Prometheus and Alertmanager.' in workspace_standard

    print('PASS — Alertmanager provider readiness is consumer-neutral and alert consumers are binding-scoped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
