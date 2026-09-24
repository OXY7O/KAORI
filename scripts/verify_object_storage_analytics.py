#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def main() -> int:
    routes = read('app/storage/object_storage/analytics/routes.py')
    analysis = read('app/storage/object_storage/analytics/analysis.py')
    service = read('app/storage/object_storage/analytics/service.py')
    pages = read('app/storage/object_storage/analytics/pages.py')
    runtime = read('app/storage/object_storage/analytics/runtime.py')
    materialization = read('app/storage/object_storage/analytics/materialization.py')
    forecast_task = read('app/storage/object_storage/analytics/tasks.py')
    forecast_job_adapter = read('app/storage/object_storage/analytics/job_adapter.py')
    bucket_table_service = read('app/storage/object_storage/analytics/bucket_table.py')
    alert_sources = read('app/storage/object_storage/analytics/alert_sources.py')
    alert_table_service = read('app/storage/object_storage/analytics/alert_table.py')
    presentation = read('app/storage/object_storage/analytics/presentation.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    resolver = read('app/storage/object_storage/analytics/sources/resolver.py')
    contracts = read('app/common/analytics/metrics/contracts.py')
    profile = read('app/integrations/observability/metrics_source/query_profiles/object_storage_v1.py')
    audit = read('app/integrations/observability/metrics_source/query_profiles/object_storage_audit.py')
    metrics_catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    alertmanager_catalog = read(
        'app/definitions/catalogs/integrations/observability/alert_source/providers/alertmanager.yaml'
    )
    alertmanager_profile_migration = read('migrations/versions/20260814_object_storage_alert_profile.py')
    binding_validation = read('app/integrations/observability/metrics_source/binding_validation.py')
    binding_validator = read('app/integrations/observability/metrics_source/binding_validators/object_storage.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    template = read('app/templates/storage/object_storage/analytics/index.html')
    alerts_summary = read('app/templates/storage/object_storage/analytics/partials/_alerts_summary.html')
    alerts_signals = read('app/templates/storage/object_storage/analytics/partials/_alerts_signal_records.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    alert_source_evidence = read('app/templates/storage/object_storage/analytics/partials/_alerts_source_evidence.html')
    alerts_workspace = read('app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html')
    boundary = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    readiness = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    bucket_table_template = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    dependency_blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    dependency_notice = read('app/templates/storage/object_storage/analytics/partials/_dependency_notice.html')
    shared_dependency_blocker = read('app/templates/components/dependencies/_blocker.html')
    hero = read('app/templates/storage/object_storage/analytics/partials/_hero.html')
    hero_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_posture.html')
    hero_blocked = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')
    forecast_worker_status = read(
        'app/templates/storage/object_storage/analytics/partials/_forecast_worker_status.html'
    )
    materialization_template = read(
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html'
    )
    overview_workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    overview_capacity = read('app/templates/storage/object_storage/analytics/partials/_overview_capacity_snapshot.html')
    overview_performance = read(
        'app/templates/storage/object_storage/analytics/partials/_overview_performance_snapshot.html'
    )
    overview_forecast = read('app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html')
    overview_consumer = read('app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html')
    record_pagination = read('app/templates/analytics/components/_record_pagination.html')
    overview_analysis = read('app/templates/storage/object_storage/analytics/partials/_overview_analysis.html')
    capacity_analysis = read('app/templates/storage/object_storage/analytics/partials/_capacity_analysis.html')
    capacity_workspace = read('app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html')
    capacity_pressure = read('app/templates/storage/object_storage/analytics/partials/_capacity_pressure.html')
    performance_analysis = read('app/templates/storage/object_storage/analytics/partials/_performance_analysis.html')
    performance_workspace = read('app/templates/storage/object_storage/analytics/partials/_performance_workspace.html')
    performance_traffic = read('app/templates/storage/object_storage/analytics/partials/_performance_traffic.html')
    forecast_analysis = read('app/templates/storage/object_storage/analytics/partials/_forecast_analysis.html')
    forecast_workspace = read('app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html')
    forecast_methodology = read('app/templates/storage/object_storage/analytics/partials/_forecast_methodology.html')
    top_consumers_workspace = read(
        'app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html'
    )
    top_consumers_storage = read('app/templates/storage/object_storage/analytics/partials/_top_consumers_storage.html')
    top_consumers_activity = read(
        'app/templates/storage/object_storage/analytics/partials/_top_consumers_activity.html'
    )
    reconciliation = read('app/templates/storage/object_storage/analytics/partials/_reconciliation.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    javascript = read('app/static/js/storage/object_storage/analytics.js')
    analytics_controls = read('app/static/js/analytics/controls.js')
    layout = read('app/templates/layouts/app.html')

    assert 'resolve_object_storage_metrics_source' in runtime
    assert 'MetricsSource' in runtime
    assert 'MetricsConsumer' not in service
    assert 'MetricsSourceError' not in service
    assert 'MetricsConsumer' not in runtime
    assert 'MetricsSourceError' in runtime
    assert 'ObjectStorageSystem' in service
    assert 'system.buckets' in service
    assert 'load_alert_stream' in service
    assert 'build_alert_table_view' in service
    assert "ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'metrics_source')" in alert_sources
    assert "required_capabilities=('alerts_v2',)" in alert_sources
    assert 'ACTIVE_ALERTS_EXPRESSION' in alert_sources
    assert 'source_wide_failure' in runtime

    assert 'class MetricsSource(Protocol)' in contracts
    assert 'class MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in contracts
    assert '_SOURCE_ADAPTERS' in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioMetricsSourceAdapter.supports' in resolver
    assert "scope_type='object_storage_system'" in adapter
    assert 'MetricsConsumer.for_asset' in adapter
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
        'object_storage_recommendations',
        'object_storage_alerts',
        'object_storage_bucket_table',
        'object_storage_alert_table',
    ):
        assert f'def {endpoint}' in routes
        assert "@permission_required('object_storage_analytics.view')" in routes
        if endpoint not in {
            'object_storage_recommendations',
            'object_storage_bucket_table',
            'object_storage_alert_table',
        }:
            assert f'analytics.{endpoint}' in menu

    assert 'profile_key: object-storage-metrics-v1' in metrics_catalog
    assert 'validation_strategy: custom' in metrics_catalog
    assert "register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'object_storage_system'" in read(
        'app/integrations/observability/metrics_source/binding_validators/__init__.py'
    )
    assert 'ObjectStorageMetricsProfileAuditor' in binding_validator
    assert 'owner = object_storage_owner(system.id)' in binding_validator
    assert "owner is not None and owner.provider_key == 'minio'" in binding_validator
    assert "'metrics_readiness': audit" in binding_validator
    assert '_VALIDATION_ADAPTERS' in binding_validator
    assert "asset_profile='minio-v2'" in binding_validator
    assert 'get_binding_validator(instance.adapter_key, binding.asset_type)' in binding_validation
    assert "profile.profile_key == 'kubernetes-metrics-v1'" not in binding_validation
    assert 'class ObjectStorageMetricsProfileAuditor' in audit
    assert 'self.client.series(metrics)' in audit
    assert 'self.client.query(definition.expression)' in audit
    assert "readiness_tier='optional'" in profile
    assert 'Operational Metrics Contract' in readiness
    assert 'Full Validation checks metric families, labels, and queries for this binding.' in readiness
    assert 'Readiness By Evidence Domain' in readiness

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

    assert 'Automatic · Alertmanager Preferred' in controls
    assert 'Metrics Source Fallback Active' in alert_sources
    assert 'Consumer Validation Stale' in alert_sources
    assert 'profile_key: object-storage-alerts-v1' in alertmanager_catalog
    assert 'minio-alerts-v1' not in alertmanager_catalog
    assert "validation_profile = 'object-storage-alerts-v1'" in alertmanager_profile_migration
    assert "validation_status = 'validation_required'" in alertmanager_profile_migration
    assert 'Provider Alerts' in alerts_summary
    assert 'Anomaly Signals' in alerts_summary
    assert 'Alert Reading' in alerts_summary
    assert 'Provider alerts and anomaly signals are separate' in alerts_summary
    assert 'Anomaly Signal Detail' in alerts_signals
    assert 'Provider Alert Records' in alert_records
    assert 'registry_ui.clear_filters_action(' in alert_records
    assert 'Alertmanager Authority' in alert_source_evidence
    assert 'Alert Lifecycle & Routing' in boundary
    assert 'Deferred' not in boundary
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
        'build_capacity_usage_view',
        'build_performance_view',
        'build_posture_view',
        'build_signal_posture',
    ):
        assert f'def {builder}' in presentation
        assert builder in service
    assert 'Prometheus' not in analysis
    assert 'MinIO' not in analysis
    assert 'Operational Health Summary' in overview_analysis
    assert 'Capacity Operating Boundary' in capacity_analysis
    assert 'Physical Capacity Utilization' in capacity_analysis
    assert 'Usage Direction' in capacity_analysis
    assert 'Quota Pressure &amp; Usage Concentration' in capacity_pressure
    assert 'Quota Evidence Coverage' in capacity_pressure
    assert 'Critical Quota' in capacity_pressure
    assert 'Bucket Capacity Records' in bucket_table_template
    assert 'progress_bar.semantic_bar(row.quota_utilization' in bucket_table_template
    assert 'Request Path Operating Boundary' in performance_analysis
    assert 'Request Reliability' in performance_analysis
    assert 'Request Processing Pressure' in performance_analysis
    assert 'Throughput &amp; Request Direction' in performance_traffic
    assert 'Increasing demand is descriptive, not automatically unhealthy' in performance_traffic
    assert 'Bucket Request Path Records' in bucket_table_template
    assert "page_key == 'performance'" in bucket_table_template
    assert 'row.request_source' in bucket_table_template
    assert 'row.error_source' in bucket_table_template
    assert "include_capacity_detail=page_key != 'performance'" in service
    assert 'Forecast Operating Boundary' in forecast_analysis
    assert 'Storage Consumer Leaders' in top_consumers_storage
    assert 'Request Activity Leaders' in top_consumers_activity
    assert 'Inventory &amp; Operational Reconciliation' in reconciliation
    assert 'data-object-storage-secondary-trend-points' in trend
    assert "label: 'Error Rate'" in javascript
    assert 'secondaryByTimestamp' in javascript
    assert 'K8s Analytics' not in menu
    assert 'Kubernetes Analytics' not in menu
    assert 'Object Storage Analytics' not in menu
    assert 'title="Kubernetes"' in menu
    assert 'aria-label="Kubernetes"' in menu
    assert '>Kubernetes</span>' in menu
    assert 'title="Object Storage"' in menu
    assert 'aria-label="Object Storage"' in menu
    assert '>Object Storage</span>' in menu

    for label in (
        'Not Configured',
        'Consumer Validation Required',
        'Consumer Validation Stale',
        'Capability Incomplete',
        'Checking Runtime',
        'Operational',
        'Degraded',
        'Disconnected',
        'Authentication Failed',
        'Runtime Query Failed',
    ):
        assert label in runtime or label in read('app/storage/object_storage/analytics/dependencies.py')
    assert 'required_contract_ready' in runtime
    assert 'metrics_runtime_blocker' in runtime
    assert 'metrics_query_blocker' in runtime
    assert "'inventory_required'" in read('app/storage/object_storage/analytics/dependencies.py')
    assert 'inventory_required_blocker(system)' in service
    assert service.count('inventory_required_blocker(system)') >= 1
    assert 'read_analytics_snapshot(system_id=system.id, time_range=time_range)' in service
    assert "source_setup(system, execution_mode='background')" in service
    assert 'build_bucket_table_view' in bucket_table_service
    assert 'default=5' in bucket_table_service
    assert "'overview': 'consumers'" not in bucket_table_service
    assert "'capacity': 'quota'" in bucket_table_service
    assert "'performance': 'buckets'" in bucket_table_service
    assert "'top_consumers': 'records'" in bucket_table_service
    assert '{5, 10, 25, 50}' in bucket_table_service
    assert 'components/loading_bar.html' in controls
    assert 'object-storage-analytics-refresh-indicator' in controls
    assert 'components/loading_bar.html' in bucket_table_template
    assert 'analytics/components/_record_pagination.html' in bucket_table_template
    assert 'object-storage-bucket-table-loading-indicator' in bucket_table_template
    assert 'components/analytics/_table_label_primitives.html' not in bucket_table_template
    assert 'components/dependencies/_blocker.html' in dependency_blocker
    assert 'Object Storage → Metrics → Analytics Snapshot' in dependency_blocker
    assert 'Alert Evidence' not in dependency_blocker
    assert 'dependency_grid_classes = "lg:grid-cols-3"' in dependency_blocker
    assert 'Analytics Setup Path' in shared_dependency_blocker
    assert 'Current Blocker' in shared_dependency_blocker
    assert 'dependency_route_summary' in shared_dependency_blocker
    assert 'dependency_step_count' in shared_dependency_blocker
    assert '_dependency_notice.html' in bucket_table_template
    assert '_dependency_notice.html' in alert_records
    assert 'dependency_blocker.diagnostic_detail' in dependency_notice
    blocker_index = template.index('{% if dependency_blocker %}')
    controls_index = template.index('partials/_controls.html')
    else_index = template.index('{% else %}', blocker_index)
    assert blocker_index < else_index < controls_index
    assert 'metrics_source.detail' not in hero
    assert 'page_hero.blocked_context_body(' in hero_blocked
    assert "'Active Scope'" in hero_blocked
    assert "'Missing Evidence'" in hero_blocked
    assert "'Current Step'" not in hero_blocked
    assert "'Progress'" not in hero_blocked
    assert "'Analytics Readiness'" in hero_blocked
    for evidence_label in ('System Context', 'Inventory Snapshot', 'Operational Metrics', 'Analytics Snapshot'):
        assert evidence_label in hero_blocked
    assert "'Overview'" in pages
    assert "'Analytics Overview'" not in pages
    for copy in (
        'Review capacity, bucket pressure, quotas, trends, and growth.',
        'Review S3 activity, errors, queue depth, demand, and traffic.',
        'Project storage growth and exhaustion risk from committed history.',
        'Rank buckets by storage, objects, requests, and concentration.',
    ):
        assert copy in pages
    assert "'Operational Posture'" in hero_posture
    assert "'Analytics Status'" in hero_posture
    assert 'components/content_tabs.html' in overview_workspace
    assert 'data-analytics-tabset' in overview_workspace
    assert 'data-analytics-preserve-tab' in controls
    assert "'Capacity & Usage'" in pages
    assert "'Performance'" in pages
    assert "'Object Storage Capacity & Usage'" not in pages
    assert "'Object Storage Performance'" not in pages
    assert "'Capacity Posture'" in hero_posture
    assert "'Capacity Status'" in hero_posture
    assert "'Performance Posture'" in hero_posture
    assert "'Request Health'" in hero_posture
    assert 'data-analytics-tabset-id="object-storage-capacity-content"' in capacity_workspace
    assert 'Capacity &amp; Usage Workspace' in capacity_workspace
    for label in ('Summary', 'Usage Trend', 'Quota & Buckets', 'Evidence'):
        assert f"'{label}'" in capacity_workspace
    assert '_capacity_analysis.html' in capacity_workspace
    assert '_trend.html' in capacity_workspace
    assert '_capacity_pressure.html' in capacity_workspace
    assert '_bucket_table.html' in capacity_workspace
    assert '_reconciliation.html' in capacity_workspace
    assert '_metrics_readiness.html' in capacity_workspace
    assert '_evidence_boundary.html' in capacity_workspace
    assert 'data-analytics-tabset-id="object-storage-performance-content"' in performance_workspace
    assert 'Performance Analysis Workspace' in performance_workspace
    for label in ('Request Health', 'Traffic & Trend', 'Bucket Activity', 'Evidence'):
        assert f"'{label}'" in performance_workspace
    assert '_performance_analysis.html' in performance_workspace
    assert '_performance_traffic.html' in performance_workspace
    assert '_trend.html' in performance_workspace
    assert '_bucket_table.html' in performance_workspace
    assert '_metrics_readiness.html' in performance_workspace
    assert '_evidence_boundary.html' in performance_workspace
    assert 'data-analytics-preserve-tab' in controls
    assert 'Automatic · Alertmanager Preferred' in controls
    assert 'build_alert_table_view' in alert_table_service
    assert "document.addEventListener('kaori:analytics-tab-visible'" in javascript
    for label in ('Capacity', 'Performance', 'Consumers', 'Forecast', 'Evidence'):
        assert f"'{label}'" in overview_workspace
    assert 'Capacity Snapshot' in overview_capacity
    assert 'Request Path Snapshot' in overview_performance
    assert 'Forecast Snapshot' in overview_forecast
    assert 'Consumer Concentration Snapshot' in overview_consumer
    assert '_overview_consumer_snapshot.html' in overview_workspace
    assert '_bucket_table.html' not in overview_workspace
    assert 'partials/_overview_workspaces.html' not in template
    assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials/_overview_workspaces.html').exists()
    assert 'analyticsTabStorageKey' in analytics_controls
    assert 'js/analytics/controls.js' in layout
    assert not (ROOT / 'app/static/js/kubernetes/analytics/controls.js').exists()
    assert 'Canonical Inventory-aligned full-page + HTMX pagination' in record_pagination
    assert 'registry_ui.clear_filters_action(' in bucket_table_template
    assert 'Bucket Consumption Evidence' not in bucket_table_template

    assert 'data-analytics-tabset-id="object-storage-forecast-content"' in forecast_workspace
    for label in ('Forecast Outlook', 'Usage Trend', 'Bucket Forecasts', 'Worker & Method', 'Evidence'):
        assert f"'{label}'" in forecast_workspace
    assert '_forecast_worker_status.html' in forecast_workspace
    assert '_forecast_methodology.html' in forecast_workspace
    assert 'Linear baseline · planning signal only' in forecast_methodology
    assert "'Forecast Posture'" in hero_posture
    assert "'Forecast Outlook'" in hero_posture

    assert 'data-analytics-tabset-id="object-storage-top-consumers-content"' in top_consumers_workspace
    for label in ('Storage Leaders', 'Request Activity', 'Consumer Records', 'Evidence'):
        assert f"'{label}'" in top_consumers_workspace
    assert '_top_consumers_storage.html' in top_consumers_workspace
    assert '_top_consumers_activity.html' in top_consumers_workspace
    assert '_bucket_table.html' in top_consumers_workspace
    assert "'Consumer Posture'" in hero_posture
    assert "'Usage Concentration'" in hero_posture

    assert 'data-analytics-tabset-id="object-storage-alerts-content"' in alerts_workspace
    for label in ('Alert Overview', 'Provider Alerts', 'Anomaly Signals', 'Recommendations', 'Evidence'):
        assert f"'{label}'" in alerts_workspace
    assert '_alerts_summary.html' in alerts_workspace
    assert '_alerts_signal_records.html' in alerts_workspace
    assert '_alert_records.html' in alerts_workspace
    assert '_alerts_source_evidence.html' in alerts_workspace
    assert "'Alert Posture'" in hero_posture
    assert "'Active Alert State'" in hero_posture
    assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials/_alerts_lifecycle.html').exists()

    for retired in ('_summary.html', '_top_consumers_analysis.html', '_alerts.html'):
        assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials' / retired).exists()

    assert 'Consumer Validation Stale' in adapter
    assert 'object-storage-metrics-v1' in adapter
    assert 'minio-metrics-2024-v1' not in adapter
    assert 'execution_mode' in resolver
    assert "execution_mode='background'" in materialization
    assert 'ObjectStorageForecastSnapshot' in materialization
    assert 'materialize_object_storage_forecasts' in forecast_task
    assert 'object_storage.forecast.materialize' in forecast_job_adapter
    assert 'FORECASTING_CELERY_QUEUE' in forecast_job_adapter
    assert 'Forecast Worker Refresh' in forecast_worker_status
    assert 'forecast_materialization.usable' in forecast_workspace
    assert 'eligible_target_count' in materialization_template
    assert 'selected_job.eligible_cluster_count' not in materialization_template
    assert (ROOT / 'app/models/object_storage_analytics.py').exists()
    assert (ROOT / 'migrations/versions/20260814_object_storage_forecast_snapshots.py').exists()
    assert (ROOT / 'migrations/versions/20260814_object_storage_metrics_profile.py').exists()

    assert not (ROOT / 'app/storage/object_storage/analytics/parsing.py').exists()
    assert not (ROOT / 'app/storage/object_storage/analytics/metrics.py').exists()

    print(
        'PASS — KAORI Object Storage Analytics · '
        'domain-analysis / metrics-source-neutral / fail-fast / inventory-separated / Alertmanager-first-fallback-safe'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
