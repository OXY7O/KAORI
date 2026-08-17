#!/usr/bin/env python3
"""Enforce KAORI bounded-context namespaces after the application package cutover."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'

FORBIDDEN_PATHS = (
    'app/storage_inventory',
    'app/inventory',
    'app/cluster',
    'app/governance',
    'app/kubernetes_operations',
    'app/metrics_sources',
    'app/alert_sources',
    'app/object_storage',
    'app/auth',
    'app/users',
    'app/rbac',
    'app/identity_providers',
    'app/jobs',
    'app/notifications',
    'app/retention',
    'app/knowledge',
    'app/resolver',
    'app/automation_control',
    'app/alert_intelligence',
    'app/notification_channels',
    'app/utils',
    'app/storage/base.py',
    'app/storage/local.py',
    'app/storage/s3.py',
    'app/storage/service.py',
    'app/templates/auth',
    'app/templates/users',
    'app/templates/cluster',
    'app/templates/governance',
    'app/templates/kubernetes_operations',
    'app/templates/inventory',
    'app/templates/jobs',
    'app/templates/notifications',
    'app/templates/analytics/kubernetes',
    'app/templates/analytics/object_storage',
    'app/templates/dashboards/kubernetes',
)

REQUIRED_PATHS = (
    'app/access/authentication',
    'app/access/identity_providers',
    'app/access/users',
    'app/access/rbac',
    'app/integrations/observability/metrics_source/application',
    'app/integrations/observability/alert_source/providers/alertmanager/application',
    'app/integrations/storage/object_storage/providers/minio/application',
    'app/integrations/delivery/notification_channels',
    'app/kubernetes/analytics',
    'app/kubernetes/inventory',
    'app/kubernetes/cluster',
    'app/kubernetes/governance',
    'app/kubernetes/operations',
    'app/kubernetes/dashboard',
    'app/storage/object_storage/analytics',
    'app/storage/object_storage/inventory',
    'app/common/analytics/metrics/contracts.py',
    'app/platform_operations/jobs',
    'app/platform_operations/notifications',
    'app/platform_operations/data_lifecycle/retention',
    'app/platform_operations/health',
    'app/intelligence/alert_intelligence',
    'app/intelligence/automation_control',
    'app/intelligence/knowledge',
    'app/intelligence/resolver',
    'app/artifact_storage',
    'app/templates/access/authentication',
    'app/templates/access/users',
    'app/templates/kubernetes/analytics',
    'app/templates/kubernetes/inventory',
    'app/templates/kubernetes/cluster',
    'app/templates/kubernetes/governance',
    'app/templates/kubernetes/operations',
    'app/templates/kubernetes/dashboard',
    'app/templates/storage/object_storage/analytics',
    'app/templates/storage/object_storage/inventory',
    'app/templates/platform_operations/jobs',
    'app/templates/platform_operations/notifications',
    'app/static/js/kubernetes/analytics',
    'app/static/js/kubernetes/inventory',
    'app/static/js/storage/object_storage/analytics.js',
)

RETIRED_IMPORT_PREFIXES = (
    'app.storage_inventory',
    'app.inventory',
    'app.cluster',
    'app.governance',
    'app.kubernetes_operations',
    'app.metrics_sources',
    'app.alert_sources',
    'app.object_storage',
    'app.auth',
    'app.users',
    'app.rbac',
    'app.identity_providers',
    'app.jobs',
    'app.notifications',
    'app.retention',
    'app.knowledge',
    'app.resolver',
    'app.automation_control',
    'app.alert_intelligence',
    'app.notification_channels',
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _absolute_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            targets.append(node.module)
    return tuple(targets)


def main() -> int:
    errors: list[str] = []

    for relative in FORBIDDEN_PATHS:
        if (ROOT / relative).exists():
            errors.append(f'retired namespace/path still exists: {relative}')

    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            errors.append(f'canonical namespace/path is missing: {relative}')

    analytics_root = ROOT / 'app/analytics'
    allowed_analytics_files = {'__init__.py', 'README.md', 'routes.py'}
    allowed_analytics_dirs = {'__pycache__'}
    if analytics_root.exists():
        for child in analytics_root.iterdir():
            if child.is_file() and child.name not in allowed_analytics_files:
                errors.append(f'analytics coordinator contains domain implementation file: {child.relative_to(ROOT)}')
            if child.is_dir() and child.name not in allowed_analytics_dirs:
                errors.append(
                    f'analytics coordinator contains domain implementation directory: {child.relative_to(ROOT)}'
                )

    for path in APP.rglob('*.py'):
        for target in _absolute_imports(path):
            if any(target == prefix or target.startswith(f'{prefix}.') for prefix in RETIRED_IMPORT_PREFIXES):
                errors.append(f'{path.relative_to(ROOT)} imports retired namespace {target}')

    service = _read('app/storage/object_storage/analytics/service.py')
    for forbidden in (
        'MetricsConsumer',
        'MetricsSourceError',
        'app.integrations.observability.metrics_source.application',
        'get_object_storage_query_expression',
    ):
        if forbidden in service:
            errors.append(f'Object Storage analytics service leaks provider-specific dependency: {forbidden}')

    contracts = _read('app/common/analytics/metrics/contracts.py')
    for required in ('class MetricsSource(Protocol)', 'class MetricsSourceError', 'class MetricsSourceIdentity'):
        if required not in contracts:
            errors.append(f'provider-neutral metrics contract is incomplete: missing {required}')

    metrics_adapter = _read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    for required in ('MetricsConsumer', 'get_object_storage_query_expression', 'retry_count=0'):
        if required not in metrics_adapter:
            errors.append(f'Object Storage Metrics Source adapter is missing provider ownership marker: {required}')

    source_resolver = _read('app/storage/object_storage/analytics/sources/resolver.py')
    for required in ('_SOURCE_ADAPTERS', "asset_profile='minio-v2'", 'MinioMetricsSourceAdapter.supports'):
        if required not in source_resolver:
            errors.append(f'Object Storage metrics source resolver is missing qualified adapter marker: {required}')

    object_storage_presentation = _read('app/storage/object_storage/inventory/presentation.py')
    for forbidden in ('product_key', 'product_label', 'Compatibility aliases'):
        if forbidden in object_storage_presentation:
            errors.append(f'Object Storage Inventory still exposes retired compatibility field: {forbidden}')

    object_storage_inventory_templates = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted((ROOT / 'app/templates/storage/object_storage/inventory').rglob('*.html'))
    )
    for forbidden in ('name="product"', 'selected_product', 'filters.product', 'inventory.products'):
        if forbidden in object_storage_inventory_templates:
            errors.append(f'Object Storage Inventory UI still exposes retired product filter contract: {forbidden}')

    object_storage_templates = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted((ROOT / 'app/templates/storage/object_storage/analytics').rglob('*.html'))
    )
    if 'Prometheus Binding Required' in object_storage_templates:
        errors.append('Object Storage analytics UI still exposes a Prometheus-specific dependency blocker.')

    binding_service = _read('app/integrations/binding_service.py')
    for forbidden in ('def create_cluster_source_binding(', 'def cluster(self)'):
        if forbidden in binding_service:
            errors.append(f'Integration binding service still exposes a domain compatibility contract: {forbidden}')

    integration_routes = _read('app/integrations/routes.py')
    for required in ('create_source_binding(', 'SourceBindingSpec(', "asset_type='kubernetes_cluster'"):
        if required not in integration_routes:
            errors.append(f'Kubernetes binding workflow is not using the canonical asset binding contract: {required}')

    platform_menu = _read('app/templates/components/navigation/platform_operations_menu.html')
    if 'Operations Center' not in platform_menu:
        errors.append('Platform Operations category must expose Operations Center as its workspace parent.')

    if errors:
        print('FAIL — KAORI Domain Namespace Architecture')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Domain Namespace Architecture')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
