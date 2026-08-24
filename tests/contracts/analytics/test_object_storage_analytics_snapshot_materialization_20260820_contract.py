from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_operational_analytics_has_persistent_snapshot_model_and_migration() -> None:
    model = read('app/models/object_storage_analytics.py')
    exports = read('app/models/__init__.py')
    migration = read('migrations/versions/20260820_object_storage_analytics_snapshots.py')

    assert 'class ObjectStorageAnalyticsSnapshot(db.Model):' in model
    assert "__tablename__ = 'object_storage_analytics_snapshots'" in model
    assert "'object_storage_system_id',\n            'time_range'" in model
    assert "status IN ('pending', 'ready', 'failed')" in model
    assert 'freshness_minutes' in model
    assert 'stale_grace_minutes' in model
    assert 'last_job_execution_id' in model
    assert 'ObjectStorageAnalyticsSnapshot' in exports
    assert "revision = '20260820_obj_analytics_snapshot'" in migration
    assert "down_revision = '20260817_activity_audit_v1'" in migration
    assert "'object_storage_analytics_snapshots'" in migration


def test_operational_snapshot_lifecycle_preserves_last_usable_payload_and_schema() -> None:
    materialization = read('app/storage/object_storage/analytics/materialization.py')

    assert "ANALYTICS_SNAPSHOT_SCHEMA = 'object-storage-analytics.v1'" in materialization
    assert 'def read_analytics_snapshot(' in materialization
    assert 'def mark_analytics_pending(' in materialization
    assert 'def store_analytics_snapshot(' in materialization
    assert 'def fail_analytics_snapshot(' in materialization
    assert 'def analytics_snapshot_due(' in materialization
    assert "'Refreshing · Last Snapshot Available'" in materialization
    assert "'Stale · Refresh Failed'" in materialization
    assert "'Snapshot Contract Invalid'" in materialization
    assert "payload.get('schema') != ANALYTICS_SNAPSHOT_SCHEMA" in materialization


def test_page_requests_are_snapshot_only_and_live_reads_are_worker_owned() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    worker_collector = service.split('def build_analytics_snapshot_payload', 1)[1].split('def _base_context', 1)[0]
    request_path = service.split('def _base_context', 1)[1]

    assert "source_setup(system, execution_mode='background')" in worker_collector
    assert 'reader = EvidenceReader(source)' in worker_collector
    assert "load_alert_stream(system, selected_source='alertmanager')" in worker_collector
    assert "load_alert_stream(system, selected_source='metrics_source')" in worker_collector
    assert (
        "for page_key in ('overview', 'capacity', 'performance', 'top_consumers', 'alerts', 'forecast')"
        in worker_collector
    )

    assert 'EvidenceReader(' not in request_path
    assert 'source_setup(' not in request_path
    assert 'load_alert_stream(' not in request_path
    assert 'alertmanager_readiness(system)' not in request_path
    assert 'read_analytics_snapshot(system_id=system.id, time_range=time_range)' in request_path
    assert "job_key='object_storage.analytics.materialize'" in request_path
    assert "return get_object_storage_analytics_context('alerts', query_args)" in request_path
    assert 'return get_object_storage_analytics_context(page_key, query_args)' in request_path


def test_one_worker_collection_reuses_metric_queries_across_page_datasets() -> None:
    runtime = read('app/storage/object_storage/analytics/runtime.py')

    assert 'self._scalar_cache: dict[str, float | None] = {}' in runtime
    assert 'self._vector_cache: dict[str, dict[str, float]] = {}' in runtime
    assert 'self._trend_cache: dict[tuple[str, str], list[MetricPoint]] = {}' in runtime
    assert 'if key in self._scalar_cache:' in runtime
    assert 'if key in self._vector_cache:' in runtime
    assert 'if cache_key in self._trend_cache:' in runtime


def test_alert_selection_is_resolved_from_worker_collected_streams() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    alerts = read('app/storage/object_storage/analytics/alert_sources.py')

    assert 'def resolve_materialized_alert_stream(' in alerts
    assert 'without live provider access' in alerts
    assert "streams.get('alertmanager')" in alerts
    assert "streams.get('metrics_source')" in alerts
    assert "'alert_streams': {" in service
    assert "'alertmanager': alertmanager_stream" in service
    assert "'metrics_source': metrics_alert_stream" in service
    assert 'resolve_materialized_alert_stream(' in service


def test_registered_object_storage_analytics_job_uses_analytics_batch_and_shared_policy_surface() -> None:
    jobs = yaml.safe_load(read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'))
    definition = next(item for item in jobs['jobs'] if item['key'] == 'object_storage.analytics.materialize')
    adapter = read('app/storage/object_storage/analytics/job_adapter.py')
    tasks = read('app/storage/object_storage/analytics/tasks.py')
    config = read('app/config/default.py')
    worker_bootstrap = read('celery_worker.py')
    routes = read('app/platform_operations/jobs/routes.py')
    presentation = read('app/platform_operations/jobs/configuration.py')
    exports = read('app/platform_operations/jobs/definitions/__init__.py')

    assert definition['name'] == 'Object Storage Analytics Data Refresh'
    assert definition['domain'] == 'Object Storage Analytics'
    assert definition['queue_name'] == 'analytics-batch'
    assert definition['workload_class'] == 'analytics'
    assert definition['operation'] == 'materialize_object_storage_analytics'
    assert definition['default_interval_minutes'] == 15
    assert (
        definition['configuration_template']
        == 'platform_operations/jobs/configuration/definitions/analytics_refresh.html'
    )
    assert definition['default_configuration']['time_ranges'] == ['24h', '7d', '30d', '60d']
    assert 'dispatch_object_storage_analytics_materialization' in adapter
    assert 'build_object_storage_analytics_materialization_context' in adapter
    assert 'materialize_object_storage_analytics' in tasks
    assert "'app.storage.object_storage.analytics.tasks.materialize_object_storage_analytics'" in config
    assert 'celery_app.loader.import_default_modules()' in worker_bootstrap
    assert "job_key in {'analytics.materialize', 'object_storage.analytics.materialize'}" in routes
    assert "'object_storage.analytics.materialize': {" in presentation
    assert "get_job_definition('object_storage.analytics.materialize')" in exports
    assert 'required_contract_diagnostic' in adapter
    assert 'required_contract_diagnostic(source)' in adapter


def test_ui_explains_snapshot_authority_and_three_stage_readiness() -> None:
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    blocked_hero = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')
    boundary = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    readiness = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')

    assert 'Pages read worker-materialized analytics snapshots' in controls
    assert 'Analytics Worker Snapshot' in controls
    assert 'Loading Committed Analytics Snapshot' in controls
    assert blocker.count('Object Storage → Metrics → Analytics Snapshot') == 2
    assert blocker.count('dependency_grid_classes = "lg:grid-cols-3"') == 2
    assert "3: 'Analytics Snapshot'" in blocked_hero
    assert 'readiness_step_count = 3' in blocked_hero
    assert 'The page reads one committed worker snapshot' in boundary
    assert 'worker collection query failed' in boundary
    assert 'evaluated separately by the analytics worker when it commits a snapshot' in readiness


def test_readme_records_two_worker_owners_and_no_live_page_query_contract() -> None:
    readme = read('app/storage/object_storage/analytics/README.md')

    assert 'Interactive page requests never query Metrics Source or Alertmanager for analytics evidence.' in readme
    assert '`object_storage.analytics.materialize` runs on the `analytics-batch` queue.' in readme
    assert '`ObjectStorageAnalyticsSnapshot`' in readme
    assert '`object_storage.forecast.materialize`' in readme
    assert 'two scheduled materialization owners, not one job per page' in readme
    assert 'unique `(object_storage_system_id, time_range)` scope' in readme


def test_object_storage_materialization_rejects_stale_worker_registry_and_recovers_orphaned_queue_slots() -> None:
    adapter = read('app/storage/object_storage/analytics/job_adapter.py')
    dispatcher = read('app/platform_operations/jobs/dispatcher.py')
    jobs_service = read('app/platform_operations/jobs/service.py')
    execution = read('app/platform_operations/jobs/execution.py')
    routes = read('app/platform_operations/jobs/routes.py')

    assert adapter.count('require_registered_worker=True') >= 2
    assert 'def ensure_task_registered_for_queue(' in dispatcher
    assert 'inspector.active_queues() or {}' in dispatcher
    assert 'destination=sorted(queue_workers)' in dispatcher
    assert 'registry_inspector.registered() or {}' in dispatcher
    assert 'do not advertise task' in dispatcher
    assert 'none returned a task registry' in dispatcher
    assert 'if require_registered_worker:' in dispatcher
    assert 'ensure_task_registered_for_queue(task=task, queue_name=queue_name)' in dispatcher

    assert 'or job.queued_at < queued_cutoff' in jobs_service
    assert "stale_reason = 'queued_start_timeout'" in jobs_service
    assert 'control.revoke(job.celery_task_id, terminate=False)' in jobs_service
    assert "job.progress_message = 'Expired before worker start'" in jobs_service

    assert 'class JobExecutionUnavailable(RuntimeError):' in execution
    assert 'if job is not None and job.is_terminal:' in execution
    assert 'is already terminal with status' in execution

    run_now = routes.split('def run_now(', 1)[1].split("@bp.post('/executions/", 1)[0]
    assert 'recover_stale_jobs()' in run_now
    assert 'except JobWorkerUnavailable as exc:' in run_now
    assert 'The job was not queued, so no active execution slot was reserved.' in run_now


def test_manual_dispatch_recovery_updates_policy_status_and_surfaces_exact_blocker() -> None:
    routes = read('app/platform_operations/jobs/routes.py')
    policy_service = read('app/platform_operations/jobs/policies/service.py')
    configuration = read('app/platform_operations/jobs/configuration.py')
    materialization = read('app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html')
    activity = read('app/templates/platform_operations/jobs/configuration/_execution_activity.html')

    run_now = routes.split('def run_now(', 1)[1].split("@bp.post('/executions/", 1)[0]
    assert run_now.count('record_job_dispatch_outcome(') >= 5
    assert "status='failed'" in run_now
    assert "status='blocked'" in run_now
    assert 'status=outcome.status' in run_now
    assert 'dispatched_at=job.queued_at' in run_now
    assert "detail=f'{type(exc).__name__}: {str(exc)[:500]}'" in run_now

    assert 'def record_job_dispatch_outcome(' in policy_service
    assert 'policy.last_dispatch_status = str(status or' in policy_service
    assert 'policy.last_dispatch_message = str(message or' in policy_service
    assert "'dispatch_attention'" in configuration
    assert "'execution_blocker'" in configuration
    assert 'A manual retry is independent of the previous scheduler failure' in materialization
    assert 'Manual Execution Blocked' in activity
    assert 'Manual dispatch is blocked until an eligible target is available.' in activity


def test_registered_job_dispatch_refreshes_catalog_for_long_lived_processes() -> None:
    registry = read('app/platform_operations/jobs/registry.py')
    dispatcher = read('app/platform_operations/jobs/dispatcher.py')

    assert 'def refresh_job_registry()' in registry
    assert 'return refresh_job_registry()' in registry
    assert 'if definition is None:' in registry
    assert 'refresh_job_registry()' in dispatcher
    assert 'definition = get_job_definition(job_key)' in dispatcher


def test_object_storage_manual_dispatch_reports_required_metric_failures_instead_of_generic_not_ready() -> None:
    materialization = read('app/storage/object_storage/analytics/materialization.py')
    adapter = read('app/storage/object_storage/analytics/job_adapter.py')

    assert 'def required_contract_status(source)' in materialization
    assert 'def required_contract_diagnostic(source, *, max_items: int = 4)' in materialization
    assert "MetricReadinessState.UNSUPPORTED: 'Metric Not Scraped'" in materialization
    assert "MetricReadinessState.NO_DATA: 'No Current Samples'" in materialization
    assert "MetricReadinessState.NOT_VALIDATED: 'Validation Required'" in materialization
    assert 'Required Metrics Contract Incomplete · {ready_count}/{total_count} Ready' in materialization
    assert 'Missing: {missing_text}{suffix}' in materialization
    assert "diagnostics.append(f'{system.name}: {required_contract_diagnostic(source)}')" in adapter
    assert 'Object Storage consumer metrics contract is not Ready.' not in adapter


def test_bucket_forecast_watch_uses_shared_kaori_table_standard() -> None:
    forecast = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecasts.html')
    forecast_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html')
    bucket_table = read('app/storage/object_storage/analytics/bucket_table.py')
    service = read('app/storage/object_storage/analytics/service.py')
    routes = read('app/storage/object_storage/analytics/routes.py')
    route_registry = read('app/analytics/routes.py')
    javascript = read('app/static/js/storage/object_storage/analytics.js')

    assert 'data-object-storage-bucket-forecast-chart-panel' in forecast
    assert 'data-object-storage-bucket-forecast-rows' in forecast
    assert 'data-object-storage-bucket-forecast-chart' in forecast
    assert 'Current vs 30-Day Projected Usage' in forecast
    assert '_bucket_forecast_table.html' in forecast

    assert 'data-kaori-object-storage-bucket-forecast-table' in forecast_table
    assert 'table_ui.filter_layout_classes()' in forecast_table
    assert 'registry_ui.clear_filters_action(' in forecast_table
    assert "table_ui.table_classes('min-w-[840px]')" in forecast_table
    assert 'table_ui.head_classes()' in forecast_table
    assert 'table_ui.header_cell_classes()' in forecast_table
    assert 'table_ui.body_classes()' in forecast_table
    assert 'table_ui.row_classes()' in forecast_table
    assert 'table_ui.cell_classes()' in forecast_table
    assert 'table_ui.title_cell(row.name' in forecast_table
    assert 'record_pagination.render(' in forecast_table
    for label in ('Bucket', 'Usage Outlook', 'Growth / Day', 'Quota Outlook', 'Forecast Watch'):
        assert f'>{label}<' in forecast_table
    forecast_head = forecast_table.split('<thead', 1)[1].split('</thead>', 1)[0]
    for retired in ('Current Usage', 'Projected 30d', 'Quota Boundary', 'Quota ETA'):
        assert f'>{retired}<' not in forecast_head

    assert 'def build_bucket_forecast_table_view(' in bucket_table
    assert "query_args.get('forecast_watch')" in bucket_table
    assert "query_args.get('forecast_history_state')" in bucket_table
    assert "query_args.get('forecast_bucket_per_page')" in bucket_table
    assert "context['bucket_forecast_table'] = build_bucket_forecast_table_view(" in service
    assert 'def get_object_storage_bucket_forecast_table_context(' in service
    assert 'def object_storage_bucket_forecast_table()' in routes
    assert "'/object-storage/forecast/buckets/table'" in route_registry
    assert "const bucketForecastChartKey = 'kaoriObjectStorageBucketForecastChart'" in javascript
    assert "type: 'bar'" in javascript
    assert "indexAxis: 'y'" in javascript
    assert "label: 'Current Usage'" in javascript
    assert "label: 'Projected 30d'" in javascript
    assert 'data-object-storage-bucket-forecast-records' not in forecast_table
