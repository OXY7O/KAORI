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
    object_storage_profile_migration = read('migrations/versions/20260814_object_storage_alert_profile.py')
    forms = read('app/alertmanager/forms.py')
    minio_service = read('app/minio/service.py')
    consumer_assets = read('app/integrations/consumer_assets.py')
    validation_template = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    scope_template = read('app/templates/alertmanager/partials/_detail_scope.html')
    binding_template = read('app/templates/alertmanager/partials/_binding_registry.html')
    binding_modal = read('app/templates/integrations/components/_observability_binding_modal.html')
    readiness_template = read('app/templates/integrations/components/_readiness_explanation.html')
    minio_index = read('app/templates/minio/index.html')
    provider_frontpage = read('app/templates/integrations/components/_provider_frontpage.html')
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
    assert "profile_key='object-storage-alerts-v1'" in profiles
    assert "asset_type='object_storage_system'" in profiles
    assert 'discover_payload_capabilities' in binding_validation
    assert 'binding.validation_evidence' in binding_validation
    assert 'binding.validation_profile' in binding_validation
    assert 'get_alert_consumer_profile' in resolver
    assert 'profile_eligible' in resolver
    assert 'Consumer validation profile' in resolver

    evaluator = resolver.split('def _evaluate_binding', 1)[1].split('def _operational_rank', 1)[0]
    assert 'binding.validation_evidence or {}' in evaluator
    assert 'instance.capabilities or {}' not in evaluator

    assert 'registered_consumer_asset_definitions' in forms
    assert "asset_type='object_storage_system'" in consumer_assets
    assert 'create_source_binding' not in minio_service

    assert 'Alertmanager Full Validation' in validation_template
    assert 'integrations/components/_readiness_explanation.html' in validation_template
    assert 'data-kaori-consumer-readiness-boundary' in readiness_template
    assert 'Consumer Binding Registry' in binding_template
    assert 'Consumer Profile' in binding_template
    assert 'observability_binding_modal.render(' in scope_template
    assert 'data-kaori-observability-binding-modal' in binding_modal

    assert 'MinIO Integrations' in minio_index
    assert 'provider_front.hero(' in minio_index
    assert 'Register Connection' in provider_frontpage
    assert 'Integration Coverage' in provider_tabs
    assert 'Connection Registry' in provider_tabs
    assert 'Validation & Capabilities' in minio_detail
    assert 'Inventory & Lifecycle' in minio_detail

    assert 'kubernetes-alerts-v1' in alertmanager_readme
    assert 'object-storage-alerts-v1' in alertmanager_readme
    assert "validation_profile = 'object-storage-alerts-v1'" in object_storage_profile_migration
    assert "validation_profile = 'minio-alerts-v1'" in object_storage_profile_migration
    assert "down_revision = '20260814_obj_forecast'" in object_storage_profile_migration
    assert 'Consumer alert contracts are binding-scoped.' in compatibility_doc
    assert 'Alertmanager consumer-profile boundary' in module_map
    assert 'Alertmanager provider validation is consumer-neutral' in workspace_standard
    assert 'MinIO mirrors Kubernetes as an asset-owner provider' in workspace_standard

    print('PASS — Alertmanager provider readiness is consumer-neutral and alert consumers are binding-scoped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
