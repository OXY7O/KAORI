#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    routes = read('app/analytics/object_storage/routes.py')
    service = read('app/analytics/object_storage/service.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    resolver = read('app/analytics/object_storage/sources/resolver.py')
    contracts = read('app/analytics/shared/metrics/contracts.py')
    profile = read('app/integrations/prometheus/query_profiles/object_storage_v1.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    template = read('app/templates/analytics/object_storage/index.html')
    alert_template = read('app/templates/analytics/object_storage/partials/_alerts.html')
    boundary = read('app/templates/analytics/object_storage/partials/_evidence_boundary.html')

    assert 'resolve_object_storage_metrics_source' in service
    assert 'MetricsSource' in service
    assert 'PrometheusConsumer' not in service
    assert 'PrometheusError' not in service
    assert 'ObjectStorageSystem' in service
    assert 'system.buckets' in service
    assert 'IntegrationBinding' in service
    assert "provider_type == 'alertmanager'" in service
    assert 'source_wide_failure' in service

    assert 'class MetricsSource(Protocol)' in contracts
    assert '_SOURCE_ADAPTERS' in resolver
    assert "metrics_provider='prometheus'" in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioPrometheusMetricsSource.supports' in resolver
    assert "scope_type='object_storage_system'" in adapter
    assert 'PrometheusConsumer.for_asset' in adapter
    assert 'retry_count=0' in adapter

    forbidden = ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3', 'minio.client')
    for token in forbidden:
        assert token not in service
        assert token not in contracts

    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
    ):
        assert f'def {endpoint}' in routes
        assert "@permission_required('analytics.view')" in routes
        assert f'analytics.{endpoint}' in menu

    for metric in (
        'minio_cluster_capacity_usable_total_bytes',
        'minio_cluster_capacity_usable_free_bytes',
        'minio_cluster_usage_total_bytes',
        'minio_cluster_usage_object_total',
        'minio_s3_requests_total',
        'minio_s3_requests_errors_total',
        'minio_bucket_usage_total_bytes',
        'minio_bucket_usage_object_total',
    ):
        assert metric in profile

    assert 'Alertmanager is optional for this release' in service
    assert 'Alertmanager lifecycle integration remains optional' in service
    assert 'Alertmanager' in alert_template
    assert 'Deferred' in boundary
    assert 'Committed Inventory' in boundary
    assert 'metrics_source.provider_label' in boundary
    assert 'kaori-analytics-page' in template

    assert not (ROOT / 'app/analytics/object_storage/parsing.py').exists()
    assert not (ROOT / 'app/analytics/object_storage/metrics.py').exists()

    print(
        'PASS — KAORI Object Storage Analytics Baseline · '
        'metrics-source-neutral / fail-fast / inventory-separated / Alertmanager-optional'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
