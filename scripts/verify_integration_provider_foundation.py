#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = (
    'app/integrations/taxonomy.py',
    'app/integrations/registry.py',
    'app/integrations/binding_service.py',
    'app/integrations/resolver.py',
    'app/integrations/validation/tasks.py',
    'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/__init__.py',
    'app/integrations/observability/metrics_source/__init__.py',
    'app/integrations/observability/metrics_source/adapter.py',
    'app/integrations/observability/metrics_source/binding_management.py',
    'app/integrations/observability/metrics_source/binding_profiles.py',
    'app/integrations/observability/metrics_source/binding_validation.py',
    'app/integrations/observability/alert_source/providers/alertmanager/__init__.py',
    'app/integrations/observability/alert_source/providers/alertmanager/adapter.py',
    'app/integrations/observability/alert_source/providers/alertmanager/binding_management.py',
    'app/integrations/storage/object_storage/providers/minio/__init__.py',
    'app/integrations/storage/object_storage/providers/minio/adapter.py',
    'app/integrations/service.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f'FAIL: {message}')


def main() -> None:
    for relative in FILES:
        source = read(relative)
        ast.parse(source, filename=relative)

    registry = read('app/integrations/registry.py')
    require('domain_key: str' in registry, 'registry must own integration domain metadata')
    require('capability_key: str' in registry, 'registry must own integration capability metadata')
    require('canonical_record_loader' in registry, 'registry must own canonical reverse loading')

    resolver = read('app/integrations/resolver.py')
    require(
        "provider_type == '" not in resolver,
        'resolver must not branch on concrete provider names',
    )
    require(
        'get_record_for_canonical(instance.id)' in resolver,
        'resolver must use the registered canonical record loader',
    )

    binding_service = read('app/integrations/binding_service.py')
    require('def create_source_binding(' in binding_service, 'generic source binding entrypoint is required')
    require(
        'if provider not in {' not in binding_service,
        'binding service must not use a concrete-provider allow-list',
    )
    require(
        'def create_cluster_source_binding(' not in binding_service,
        'Domain compatibility binding wrappers must remain removed',
    )
    require('def cluster(self)' not in binding_service, 'Created binding results must not expose compatibility aliases')

    validation = read('app/integrations/validation/tasks.py')
    full_validation = validation.split('def validate_integration_instance', 1)[1].split('def _as_result_payload', 1)[0]
    require(
        "provider_type == '" not in full_validation,
        'full validation must not branch on concrete provider names',
    )
    require(
        "if 'binding.validate' in module.operations" in full_validation,
        'full validation must discover binding validation through registered operations',
    )

    service = read('app/integrations/service.py')
    catalog = service.split('def _catalog', 1)[1].split('def _ordered_status_options', 1)[0]
    require('for module in registry.all()' in catalog, 'provider catalog must be registry-driven')
    require('S3-compatible Storage' not in catalog, 'storage must be a domain, not a fake S3 provider entry')

    profiles = read('app/integrations/observability/metrics_source/binding_profiles.py')
    require(
        'register_binding_validation_profile' in profiles,
        'Metrics Source binding validation must expose asset-specific profile registration',
    )

    print('PASS: Integration provider foundation is taxonomy-driven, asset-bound, and provider-extensible.')


if __name__ == '__main__':
    main()
