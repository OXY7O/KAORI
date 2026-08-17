#!/usr/bin/env python3
"""Enforce direct-cutover domain namespaces and provider-neutral analytics boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'

FORBIDDEN_PATHS = (
    'app/storage_inventory',
    'app/inventory/collectors',
    'app/inventory/resources',
    'app/inventory/topology',
    'app/inventory/formatting.py',
    'app/inventory/job_adapter.py',
    'app/inventory/overview.py',
    'app/inventory/persistence.py',
    'app/inventory/routes.py',
    'app/inventory/synchronization.py',
    'app/analytics/alerts',
    'app/analytics/capacity',
    'app/analytics/common',
    'app/analytics/forecast',
    'app/analytics/materialization',
    'app/analytics/overview',
    'app/analytics/storage',
    'app/analytics/top_consumers',
    'app/analytics/utilization',
    'app/analytics/workload',
    'app/analytics/job_adapter.py',
    'app/analytics/tasks.py',
    'app/analytics/object_storage/metrics.py',
    'app/analytics/object_storage/parsing.py',
    'app/templates/object_storage_inventory',
    'app/templates/inventory/components',
    'app/templates/inventory/configuration',
    'app/templates/inventory/ingresses',
    'app/templates/inventory/namespaces',
    'app/templates/inventory/nodes',
    'app/templates/inventory/overview',
    'app/templates/inventory/pods',
    'app/templates/inventory/services',
    'app/templates/inventory/storage',
    'app/templates/inventory/topology',
    'app/templates/inventory/workloads',
    'app/templates/analytics/alerts',
    'app/templates/analytics/capacity',
    'app/templates/analytics/forecast',
    'app/templates/analytics/materialization',
    'app/templates/analytics/overview',
    'app/templates/analytics/storage',
    'app/templates/analytics/top_consumers',
    'app/templates/analytics/utilization',
    'app/templates/analytics/workload',
    'app/static/js/analytics_controls.js',
    'app/static/js/analytics_forecast_chart.js',
    'app/static/js/analytics_overview.js',
    'app/static/js/analytics_utilization.js',
    'app/static/js/object_storage_analytics.js',
    'app/static/js/inventory/topology.js',
    'tests/storage_inventory',
    'tests/contracts/storage_inventory',
    'tests/debug/storage_inventory',
)

REQUIRED_PATHS = (
    'app/analytics/kubernetes',
    'app/analytics/object_storage/sources/providers/minio/metrics.py',
    'app/analytics/object_storage/sources/resolver.py',
    'app/analytics/shared/metrics/contracts.py',
    'app/inventory/kubernetes',
    'app/inventory/object_storage',
    'app/templates/analytics/kubernetes',
    'app/templates/analytics/object_storage',
    'app/templates/inventory/kubernetes',
    'app/templates/inventory/object_storage',
    'app/static/js/analytics/kubernetes',
    'app/static/js/analytics/object_storage.js',
    'app/static/js/inventory/kubernetes/topology.js',
    'tests/inventory/kubernetes',
    'tests/inventory/object_storage',
    'tests/contracts/inventory/object_storage',
)

RETIRED_IMPORT_PREFIXES = (
    'app.storage_inventory',
    'app.inventory.collectors',
    'app.inventory.resources',
    'app.inventory.topology',
    'app.inventory.formatting',
    'app.inventory.job_adapter',
    'app.inventory.overview',
    'app.inventory.persistence',
    'app.inventory.routes',
    'app.inventory.synchronization',
    'app.analytics.alerts',
    'app.analytics.capacity',
    'app.analytics.common',
    'app.analytics.forecast',
    'app.analytics.materialization',
    'app.analytics.overview',
    'app.analytics.storage',
    'app.analytics.top_consumers',
    'app.analytics.utilization',
    'app.analytics.workload',
    'app.analytics.job_adapter',
    'app.analytics.tasks',
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _import_target(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [node.module or '']
    return []


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
    allowed_analytics_dirs = {'kubernetes', 'object_storage', 'shared', '__pycache__'}
    for child in analytics_root.iterdir():
        if child.is_file() and child.name not in allowed_analytics_files:
            errors.append(f'analytics capability root contains domain implementation file: {child.relative_to(ROOT)}')
        if child.is_dir() and child.name not in allowed_analytics_dirs:
            errors.append(
                f'analytics capability root contains non-canonical domain directory: {child.relative_to(ROOT)}'
            )

    inventory_root = ROOT / 'app/inventory'
    allowed_inventory_files = {'__init__.py', 'README.md'}
    allowed_inventory_dirs = {'kubernetes', 'object_storage', '__pycache__'}
    for child in inventory_root.iterdir():
        if child.is_file() and child.name not in allowed_inventory_files:
            errors.append(f'inventory capability root contains domain implementation file: {child.relative_to(ROOT)}')
        if child.is_dir() and child.name not in allowed_inventory_dirs:
            errors.append(
                f'inventory capability root contains non-canonical domain directory: {child.relative_to(ROOT)}'
            )

    for path in APP.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            for target in _import_target(node):
                if any(target == prefix or target.startswith(f'{prefix}.') for prefix in RETIRED_IMPORT_PREFIXES):
                    errors.append(
                        f'{path.relative_to(ROOT)}:{getattr(node, "lineno", 0)} imports retired namespace {target}'
                    )

    service = _read('app/analytics/object_storage/service.py')
    for forbidden in (
        'MetricsConsumer',
        'MetricsSourceError',
        'app.metrics_sources',
        'app.integrations.observability.metrics_source',
        'get_object_storage_query_expression',
    ):
        if forbidden in service:
            errors.append(f'Object Storage analytics service leaks provider-specific dependency: {forbidden}')

    contracts = _read('app/analytics/shared/metrics/contracts.py')
    for required in ('class MetricsSource(Protocol)', 'class MetricsSourceError', 'class MetricsSourceIdentity'):
        if required not in contracts:
            errors.append(f'provider-neutral metrics contract is incomplete: missing {required}')

    metrics_adapter = _read('app/analytics/object_storage/sources/providers/minio/metrics.py')
    for required in ('MetricsConsumer', 'get_object_storage_query_expression', 'retry_count=0'):
        if required not in metrics_adapter:
            errors.append(f'Object Storage Metrics Source adapter is missing provider ownership marker: {required}')

    source_resolver = _read('app/analytics/object_storage/sources/resolver.py')
    for required in (
        '_SOURCE_ADAPTERS',
        "asset_profile='minio-v2'",
        'MinioMetricsSourceAdapter.supports',
    ):
        if required not in source_resolver:
            errors.append(f'Object Storage metrics source resolver is missing qualified adapter marker: {required}')

    object_storage_presentation = _read('app/inventory/object_storage/presentation.py')
    for forbidden in ('product_key', 'product_label', 'Compatibility aliases'):
        if forbidden in object_storage_presentation:
            errors.append(f'Object Storage Inventory still exposes retired compatibility field: {forbidden}')

    object_storage_inventory_templates = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted((ROOT / 'app/templates/inventory/object_storage').rglob('*.html'))
    )
    for forbidden in ('name="product"', 'selected_product', 'filters.product', 'inventory.products'):
        if forbidden in object_storage_inventory_templates:
            errors.append(f'Object Storage Inventory UI still exposes retired product filter contract: {forbidden}')

    object_storage_templates = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in sorted((ROOT / 'app/templates/analytics/object_storage').rglob('*.html'))
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
