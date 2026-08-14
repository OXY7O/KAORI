#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    routes = read('app/analytics/object_storage/routes.py')
    analysis = read('app/analytics/object_storage/analysis.py')
    service = read('app/analytics/object_storage/service.py')
    runtime = read('app/analytics/object_storage/runtime.py')
    bucket_table_service = read('app/analytics/object_storage/bucket_table.py')
    presentation = read('app/analytics/object_storage/presentation.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    resolver = read('app/analytics/object_storage/sources/resolver.py')
    contracts = read('app/analytics/shared/metrics/contracts.py')
    profile = read('app/integrations/prometheus/query_profiles/object_storage_v1.py')
    audit = read('app/integrations/prometheus/query_profiles/object_storage_audit.py')
    binding_profiles = read('app/integrations/prometheus/binding_profiles.py')
    binding_validation = read('app/integrations/prometheus/binding_validation.py')
    binding_validator = read('app/integrations/prometheus/binding_validators/object_storage.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    template = read('app/templates/analytics/object_storage/index.html')
    alert_template = read('app/templates/analytics/object_storage/partials/_alerts.html')
    boundary = read('app/templates/analytics/object_storage/partials/_evidence_boundary.html')
    readiness = read('app/templates/analytics/object_storage/partials/_metrics_readiness.html')
    controls = read('app/templates/analytics/object_storage/partials/_controls.html')
    bucket_table_template = read('app/templates/analytics/object_storage/partials/_bucket_table.html')
    dependency_blocker = read('app/templates/analytics/object_storage/partials/_dependency_blocker.html')
    overview_workspaces = read('app/templates/analytics/object_storage/partials/_overview_workspaces.html')
    record_pagination = read('app/templates/analytics/components/_record_pagination.html')
    overview_analysis = read('app/templates/analytics/object_storage/partials/_overview_analysis.html')
    capacity_analysis = read('app/templates/analytics/object_storage/partials/_capacity_analysis.html')
    performance_analysis = read('app/templates/analytics/object_storage/partials/_performance_analysis.html')
    forecast_analysis = read('app/templates/analytics/object_storage/partials/_forecast_analysis.html')
    top_consumers_analysis = read('app/templates/analytics/object_storage/partials/_top_consumers_analysis.html')
    reconciliation = read('app/templates/analytics/object_storage/partials/_reconciliation.html')
    trend = read('app/templates/analytics/object_storage/partials/_trend.html')
    javascript = read('app/static/js/analytics/object_storage.js')

    assert 'resolve_object_storage_metrics_source' in runtime
    assert 'MetricsSource' in runtime
    assert 'PrometheusConsumer' not in service
    assert 'PrometheusError' not in service
    assert 'PrometheusConsumer' not in runtime
    assert 'PrometheusError' not in runtime
    assert 'ObjectStorageSystem' in service
    assert 'system.buckets' in service
    assert 'IntegrationBinding' in service
    assert "provider_type == 'alertmanager'" in service
    assert 'source_wide_failure' in runtime

    assert 'class MetricsSource(Protocol)' in contracts
    assert 'class MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in contracts
    assert '_SOURCE_ADAPTERS' in resolver
    assert "metrics_provider='prometheus'" in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioPrometheusMetricsSource.supports' in resolver
    assert "scope_type='object_storage_system'" in adapter
    assert 'PrometheusConsumer.for_asset' in adapter
    assert 'retry_count=0' in adapter
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in adapter

    forbidden = ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3', 'minio.client')
    for token in forbidden:
        assert token not in service
        assert token not in runtime
        assert token not in contracts

    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
        'object_storage_bucket_table',
    ):
        assert f'def {endpoint}' in routes
        assert "@permission_required('analytics.view')" in routes
        if endpoint != 'object_storage_bucket_table':
            assert f'analytics.{endpoint}' in menu


    assert "profile_key='object-storage-metrics-v1'" in binding_profiles
    assert "validation_strategy='custom'" in binding_profiles
    assert "register_binding_validator('object_storage_system'" in read(
        'app/integrations/prometheus/binding_validators/__init__.py'
    )
    assert 'ObjectStoragePrometheusProfileAuditor' in binding_validator
    assert 'return system.minio_connection is not None' in binding_validator
    assert "'metrics_readiness': audit" in binding_validator
    assert '_VALIDATION_ADAPTERS' in binding_validator
    assert "asset_profile='minio-v2'" in binding_validator
    assert 'get_binding_validator(binding.asset_type)' in binding_validation
    assert "profile.profile_key == 'kubernetes-metrics-v1'" not in binding_validation
    assert 'class ObjectStoragePrometheusProfileAuditor' in audit
    assert 'self.client.series(metrics)' in audit
    assert 'self.client.query(definition.expression)' in audit
    assert "readiness_tier='optional'" in profile
    assert 'Operational Metrics Readiness' in readiness
    assert 'Persisted validation evidence' in readiness

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
    assert 'Critical Signals' in alert_template
    assert 'Signal Reading' in alert_template
    assert 'Deferred' in boundary
    assert 'Committed Inventory' in boundary
    assert 'metrics_source.provider_label' in boundary
    assert 'kaori-analytics-page' in template

    for symbol in (
        'derive_headroom',
        'summarize_trend',
        'compare_evidence',
        'capacity_posture',
        'performance_posture',
        'forecast_posture',
        'metric_risk_signals',
    ):
        assert f'def {symbol}' in analysis
    for builder in (
        'build_trend_view',
        'build_comparison_view',
        'build_bucket_analysis',
        'build_posture_view',
        'build_signal_posture',
    ):
        assert f'def {builder}' in presentation
        assert builder in service
    assert 'Prometheus' not in analysis
    assert 'MinIO' not in analysis
    assert 'Operational Health Summary' in overview_analysis
    assert 'Capacity Operating Boundary' in capacity_analysis
    assert 'Request Operating Boundary' in performance_analysis
    assert 'Forecast Operating Boundary' in forecast_analysis
    assert 'Top Consumer Snapshot' in top_consumers_analysis
    assert 'Inventory &amp; Operational Reconciliation' in reconciliation
    assert 'data-object-storage-secondary-trend-points' in trend
    assert "label: 'Error Rate'" in javascript
    assert 'secondaryByTimestamp' in javascript
    assert 'K8s Analytics' not in menu
    assert 'Kubernetes Analytics' in menu


    for label in (
        'Not Configured',
        'Validation Required',
        'Capability Incomplete',
        'Checking Runtime',
        'Operational',
        'Degraded',
        'Disconnected',
        'Authentication Failed',
        'Runtime Query Failed',
    ):
        assert label in runtime or label in read('app/analytics/object_storage/dependencies.py')
    assert 'required_contract_ready' in runtime
    assert 'metrics_runtime_blocker' in runtime
    assert 'metrics_query_blocker' in runtime
    assert 'build_bucket_table_view' in bucket_table_service
    assert "default=5" in bucket_table_service
    assert "{5, 10, 25, 50}" in bucket_table_service
    assert 'components/loading_bar.html' in controls
    assert 'object-storage-analytics-refresh-indicator' in controls
    assert 'components/loading_bar.html' in bucket_table_template
    assert 'analytics/components/_record_pagination.html' in bucket_table_template
    assert 'object-storage-bucket-table-loading-indicator' in bucket_table_template
    assert 'components/analytics/_table_label_primitives.html' not in bucket_table_template
    assert 'Object Storage Analytics Readiness' in dependency_blocker
    assert 'Alertmanager is not a blocking dependency' in dependency_blocker
    assert 'Analysis Workspace Snapshot' in overview_workspaces
    assert "analytics.object_storage_capacity" in overview_workspaces
    assert 'Canonical Inventory-aligned full-page + HTMX pagination' in record_pagination

    assert not (ROOT / 'app/analytics/object_storage/parsing.py').exists()
    assert not (ROOT / 'app/analytics/object_storage/metrics.py').exists()

    print(
        'PASS — KAORI Object Storage Analytics · '
        'domain-analysis / metrics-source-neutral / fail-fast / inventory-separated / Alertmanager-optional'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
