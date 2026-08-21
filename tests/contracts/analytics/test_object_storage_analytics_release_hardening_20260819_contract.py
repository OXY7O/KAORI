from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_bucket_query_contract_collects_complete_scoped_vectors_without_topk_truncation() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/object_storage_v1.py')

    assert "expression='max by (bucket) (minio_bucket_usage_total_bytes)'" in profile
    assert "expression='max by (bucket) (minio_bucket_usage_object_total)'" in profile
    assert "expression='sum by (bucket) (rate(minio_bucket_requests_total[5m]))'" in profile
    assert '__name__=~"minio_bucket_requests_(4xx|5xx)_errors_total"' not in profile
    assert 'rate(minio_bucket_requests_4xx_errors_total[5m])' in profile
    assert 'rate(minio_bucket_requests_5xx_errors_total[5m])' in profile
    assert 'or sum by (bucket) (rate(minio_bucket_requests_4xx_errors_total[5m]))' in profile
    assert 'or sum by (bucket) (rate(minio_bucket_requests_5xx_errors_total[5m]))' in profile
    assert "'object_storage.bucket.usage_history': QueryDefinition(" in profile
    assert 'topk(50' not in profile


def test_bucket_evidence_keeps_inventory_fallback_and_explicit_missing_reasons() -> None:
    bucket_evidence = read('app/storage/object_storage/analytics/bucket_evidence.py')
    bucket_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    evidence = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')

    assert "return float(inventory_value), 'Committed Snapshot'" in bucket_evidence
    assert "'state': 'not_configured'" in bucket_evidence
    assert "'source': 'Committed Snapshot'" in bucket_evidence
    assert "'not_configured': ('Not Configured', 'Not Applicable', 'No Quota Configured', 'info')" in bucket_evidence
    assert "'not_collected': ('N/A', 'Unknown', 'Quota Not Collected', 'warning')" in bucket_evidence
    assert "'not_supported': ('N/A', 'Not Available', 'Quota Collection Unsupported', 'unknown')" in bucket_evidence
    assert "'unsupported': 'Metric Not Scraped'" in bucket_evidence
    assert "'failed': 'Runtime Query Failed'" in bucket_evidence
    assert 'row.request_source' in bucket_table
    assert 'row.error_source' in bucket_table
    assert 'This is actual state, not a collection failure.' in evidence
    assert '/minio/v2/metrics/bucket' in evidence


def test_quota_evidence_coverage_counts_explicit_not_configured_as_observed_state() -> None:
    presentation = read('app/storage/object_storage/analytics/presentation.py')
    capacity = read('app/templates/storage/object_storage/analytics/partials/_capacity_pressure.html')

    assert "quota_not_configured = [row for row in rows if row.get('quota_state') == 'not_configured']" in presentation
    assert "'quota_observed_count': len(quota_observed)" in presentation
    assert "'quota_not_configured_count': len(quota_not_configured)" in presentation
    assert "quota_status = 'No Quotas Configured'" in presentation
    assert 'have an observed quota state' in capacity
    assert 'explicitly report no configured quota' in capacity


def test_forecast_worker_materializes_system_and_bucket_history_in_one_snapshot() -> None:
    contracts = read('app/common/analytics/metrics/contracts.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    materialization = read('app/storage/object_storage/analytics/materialization.py')
    service = read('app/storage/object_storage/analytics/service.py')

    assert 'def trend_vector(self, metric_key: str, time_range: str, label: str)' in contracts
    assert 'def _matrix_by_label(' in adapter
    assert 'def trend_vector(self, metric_key: str, time_range: str, label: str)' in adapter
    assert "source.trend_vector('object_storage.bucket.usage_history', history_window, 'bucket')" in materialization
    assert 'names = sorted(set(inventory) | set(series))' in materialization
    assert "'history_state': history_state" in materialization
    assert "'bucket_forecasts': bucket_forecasts" in materialization
    assert "context['metrics']['bucket_forecasts'] = bucket_forecasts" in service
    assert "context['metrics']['bucket_forecast_summary']" in service


def test_forecast_workspaces_show_system_graph_and_bucket_watch_without_new_job_surface() -> None:
    overview_forecast = read('app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html')
    forecast_analysis = read('app/templates/storage/object_storage/analytics/partials/_forecast_analysis.html')
    forecast_workspace = read('app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html')
    bucket_forecasts = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecasts.html')
    bucket_forecast_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    javascript = read('app/static/js/storage/object_storage/analytics.js')
    readme = read('app/storage/object_storage/analytics/README.md')

    assert 'object_storage_trend_mode = "forecast"' in overview_forecast
    assert 'object_storage_trend_mode = "forecast"' in forecast_analysis
    assert "('buckets', 'Bucket Forecasts', 'container')" in forecast_workspace
    assert '_bucket_forecasts.html' in forecast_workspace
    assert 'Bucket Forecast Watch' in bucket_forecasts
    assert 'planning watch signals, not active Alertmanager alerts' in bucket_forecasts
    assert 'data-object-storage-bucket-forecast-chart-panel' in bucket_forecasts
    assert 'data-object-storage-bucket-forecast-chart' in bucket_forecasts
    assert '_bucket_forecast_table.html' in bucket_forecasts
    assert 'data-kaori-object-storage-bucket-forecast-table' in bucket_forecast_table
    assert 'table_ui.title_cell(row.name' in bucket_forecast_table
    assert 'data-object-storage-projection-points' in trend
    assert 'Storage Usage Forecast' in trend
    assert "const isForecast = mode === 'forecast'" in javascript
    assert "label: '30d Linear Projection'" in javascript
    assert "const bucketForecastChartKey = 'kaoriObjectStorageBucketForecastChart'" in javascript
    assert "label: 'Projected 30d'" in javascript
    assert "indexAxis: 'y'" in javascript
    assert 'does not require another job or database table' in readme


def test_shared_evidence_tab_explains_authority_and_na_states_once_for_all_object_storage_pages() -> None:
    boundary = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    readiness = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')

    for marker in (
        'How Evidence Is Assembled',
        'Committed Inventory',
        'Operational Time-Series',
        'Alert Lifecycle & Routing',
        'How To Read Missing Or Non-Applicable Values',
        'Not Configured',
        'No Current Samples',
        'Metric Not Scraped',
        'Runtime Query Failed',
    ):
        assert marker in boundary
    assert 'Operational Metrics Contract' in readiness
    assert 'Readiness By Evidence Domain' in readiness
    assert 'data-kaori-evidence-domain-readiness' in readiness
    assert 'md:grid-cols-2 xl:grid-cols-4' in readiness
    assert 'xl:grid-cols-3' not in readiness
    assert 'Required Gate' in readiness
    assert 'Domain Coverage' in readiness
    assert 'overflow-x-auto' not in readiness


def test_active_alert_records_use_responsive_kaori_htmx_record_surface_without_horizontal_scroll() -> None:
    records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')

    assert 'object-storage-alert-records-loading' in records
    assert (
        "hx-trigger=\"change[event.target.matches('select')] delay:120ms, keyup[event.target.name === 'alert_q'] changed delay:450ms, search[event.target.name === 'alert_q']\""
        in records
    )
    assert 'hx-target="#object-storage-alert-records"' in records
    assert 'hx-sync="#object-storage-alert-records:replace"' in records
    assert 'data-kaori-clear-filters' not in records  # emitted by the shared clear_filters_action macro
    assert 'clear_filters_action' in records
    assert 'alert_filters_active' in records
    assert 'Apply Filter' not in records
    assert 'overflow-x-auto' not in records
    assert 'min-w-[1120px]' not in records
    assert '<table' not in records
    assert 'data-kaori-object-storage-alert-record-list' in records
    assert 'lg:grid-cols-12' in records


def test_object_storage_analytics_readme_records_collection_and_na_ownership() -> None:
    readme = read('app/storage/object_storage/analytics/README.md')

    assert 'query profiles must not truncate the source vector with `topk`' in readme
    assert '`Metric Not Scraped`' in readme
    assert '`No Current Samples`' in readme
    assert '`No Bucket Series`' in readme
    assert '`Runtime Query Failed`' in readme
    assert '`Not Configured` is a successfully observed provider state' in readme
    assert 'never for request-path rate or error-rate time series' in readme
