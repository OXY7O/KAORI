from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_analytics_status_does_not_run_duplicate_health_query() -> None:
    consumer = _read('app/prometheus/consumer.py')
    utilization = _read('app/analytics/kubernetes/utilization/service.py')
    base = _read('app/analytics/kubernetes/common/base_service.py')
    profile = _read('app/integrations/prometheus/query_profiles/kubernetes_v1.py')
    presentation = _read('app/analytics/kubernetes/common/presentation.py')

    assert 'def analytics_status' in consumer
    assert 'vector(1)' not in consumer
    assert 'consumer.analytics_status()' in utilization
    assert 'consumer.analytics_status()' in base
    assert 'analytics.utilization.queries.PROMETHEUS_HEALTH' not in profile
    assert 'get_prometheus_status_snapshot' in utilization
    assert "'status_label': status_label" in presentation
    assert "status_label = 'Query Ready'" in presentation


def test_prometheus_queries_reuse_clients_retry_transient_failures_and_keep_fingerprints() -> None:
    consumer = _read('app/prometheus/consumer.py')
    client = _read('app/integrations/prometheus/client.py')
    runtime = _read('app/common/provider_query_runtime.py')

    assert 'self._client_cache' in consumer
    assert 'PROMETHEUS_ANALYTICS_QUERY_RETRIES' in consumer
    assert 'PROMETHEUS_ANALYTICS_RETRY_BACKOFF_SECONDS' in consumer
    assert '_TRANSIENT_HTTP_STATUS_TOKENS' in consumer
    assert 'query_fingerprint' in consumer
    assert 'record_provider_retry()' in consumer
    assert 'requests.Session()' in client
    assert 'self.session.get(' in client
    assert 'query_fingerprints' in runtime
    assert 'last_error' in runtime
    assert 'def _build_client' not in consumer


def test_provider_scoped_lock_serializes_shared_heavy_sources() -> None:
    source_lock = _read('app/analytics/kubernetes/materialization/source_lock.py')
    tasks = _read('app/analytics/kubernetes/tasks.py')

    assert 'pg_try_advisory_lock' in source_lock
    assert 'pg_advisory_unlock' in source_lock
    assert 'ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS' in source_lock
    assert 'analytics_source_lock(' in tasks
    assert 'source_lock_wait_ms' in tasks
    assert 'Could not resolve provider-specific analytics query locks' in source_lock
    assert "requested_source in {'auto', 'prometheus'}" in source_lock
    assert 'for lock_name in lock_names' in source_lock


def test_materialization_prioritizes_current_datasets_and_scales_task_budget() -> None:
    catalog = _read('app/analytics/kubernetes/materialization/catalog.py')
    adapter = _read('app/analytics/kubernetes/job_adapter.py')
    tasks = _read('app/analytics/kubernetes/tasks.py')
    config = _read('app/config/default.py')

    assert 'execution_priority: int = 100' in catalog
    assert "key='analytics.utilization.summary'" in catalog
    assert 'execution_priority=30' in catalog
    assert "key='analytics.utilization.trend'" in catalog
    assert 'execution_priority=90' in catalog
    assert 'work_items.sort(key=_work_item_sort_key)' in adapter
    assert 'def dataset_task_budget_seconds' in catalog
    assert 'dataset_task_budget_seconds(' in adapter
    assert 'dataset_task_budget_seconds(dataset_key, parameters)' in tasks
    assert 'estimated_duration_seconds' in adapter
    assert 'ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS' in config
    assert 'FORECASTING_TASK_MAX_SOFT_TIME_LIMIT_SECONDS' in config
    assert 'CELERY_VISIBILITY_TIMEOUT_SECONDS' in config
    assert '18000' in config


def test_worker_preserves_stale_data_and_records_actionable_failure_details() -> None:
    tasks = _read('app/analytics/kubernetes/tasks.py')
    errors = _read('app/analytics/kubernetes/materialization/errors.py')
    service = _read('app/analytics/kubernetes/materialization/service.py')
    presentation = _read('app/analytics/kubernetes/materialization/presentation.py')

    assert 'classify_analytics_failure' in tasks
    assert 'analytics_failure_remediation' in tasks
    assert "'query_count'" in tasks
    assert 'AnalyticsDependencyError' in tasks
    assert "snapshot.status = 'failed'" in service
    assert 'snapshot.payload_json' not in service.split('def fail_snapshot', 1)[1]
    assert 'provider_overloaded' in errors
    assert 'provider_timeout' in errors
    assert 'parse_materialization_error' in presentation
    assert 'materialization_job_url' in presentation


def test_forecast_and_top_consumers_do_not_hide_provider_failures_as_empty_data() -> None:
    base = _read('app/analytics/kubernetes/common/base_service.py')
    forecast = _read('app/analytics/kubernetes/forecast/service.py')
    top_consumers = _read('app/analytics/kubernetes/top_consumers/service.py')

    base_query = base.split('def get_prometheus_result', 1)[1].split('def extract_value', 1)[0]
    assert 'except Exception' not in base_query
    assert 'raise PrometheusError' in base_query

    forecast_range = forecast.split('def _query_range', 1)[1].split('def get_forecast_analysis_context', 1)[0]
    assert 'except Exception' not in forecast_range
    assert 'return []' not in forecast_range
    assert 'return 0.0' not in forecast_range

    materialization_context = top_consumers.split('def get_top_consumers_context', 1)[1].split(
        'def render_namespace_query', 1
    )[0]
    assert 'Top consumers query failed' not in materialization_context
    assert 'consumer_payload = top_consumers_service.get_top_consumers_payload' in materialization_context


def test_pending_ui_uses_determinate_progress_and_clear_remediation() -> None:
    pending = _read('app/templates/analytics/kubernetes/materialization/_pending.html')
    routes = _read('app/analytics/routes.py')

    assert 'animate-pulse' not in pending
    assert 'transition-all' not in pending
    assert 'progress_bar.bar(' in pending
    assert 'Recommended Action' in pending
    assert 'Job Log' in pending
    assert 'hx-sync="this:replace"' in pending
    assert "Cache-Control'] = 'no-store, max-age=0'" in routes
    assert not Path('app/templates/analytics/kubernetes/materialization/_freshness.html').exists()
    workspace = _read('app/templates/analytics/kubernetes/components/_analysis_workspace.html')
    assert 'last_error_detail' in workspace
    assert 'last_error_remediation' in workspace
    assert '{{ snapshot.last_error }}' not in workspace
    presentation = _read('app/analytics/kubernetes/materialization/presentation.py')
    assert "context.get('analytics_runtime')" in presentation
    assert "'runtime': runtime" in presentation


def test_default_analytics_policy_refreshes_current_snapshots_before_they_age_out() -> None:
    definition = _read('app/jobs/definitions/analytics_refresh.py')
    env_example = _read('.env.example')

    assert 'default_interval_minutes=15' in definition
    assert "'freshness_minutes': 15" in definition
    assert 'PROMETHEUS_ANALYTICS_QUERY_RETRIES=2' in env_example
    assert 'ANALYTICS_SOURCE_LOCK_TIMEOUT_SECONDS=900' in env_example
    assert 'ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS=7200' in env_example
    assert 'CELERY_VISIBILITY_TIMEOUT_SECONDS=18000' in env_example


def test_persisted_runtime_health_is_advisory_for_worker_and_page_dispatch() -> None:
    common_context = _read('app/analytics/kubernetes/common/context.py')
    requests = _read('app/analytics/kubernetes/materialization/requests.py')

    assert "'label': 'Prometheus Query Ready'" in common_context
    assert "base_context['prometheus_connected'] = True" in common_context
    assert 'previous runtime observation' in common_context
    candidate_function = requests.split('def _candidate_is_usable', 1)[1].split('def _prometheus_resolution', 1)[0]
    assert 'candidate is not None' in candidate_function
    assert 'operational_state not in' not in candidate_function
    assert 'runtime_warning' in requests


def test_optional_alert_anomaly_failures_are_visible_as_partial_data() -> None:
    anomalies = _read('app/analytics/kubernetes/alerts/anomalies.py')
    application = _read('app/analytics/kubernetes/alerts/application.py')
    filters = _read('app/templates/analytics/kubernetes/alerts/partials/_filters.html')

    assert '-> tuple[list[dict[str, Any]], dict[str, Any]]' in anomalies
    assert 'partial = bool(errors)' in anomalies
    assert "'available_queries': available_queries" in anomalies
    assert "'failed_queries': sorted(errors)" in anomalies
    assert 'collection_warnings' in application
    assert 'Prometheus Anomaly Evidence Is Partial' in application
    assert 'Prometheus Anomaly Evidence Is Unavailable' in application
    assert 'collection_warnings|default([])' in filters
    assert 'Source Evidence Incomplete' in filters


def test_prometheus_clients_are_created_lazily_for_cluster_scoped_queries() -> None:
    consumer = _read('app/prometheus/consumer.py')
    service = _read('app/prometheus/service.py')

    init_block = consumer.split('def __init__', 1)[1].split('def query', 1)[0]
    assert 'self.client =' not in init_block
    assert 'self.client = None' in service
    assert 'self.instance = self.consumer.config' in service


def test_unused_live_alert_comparison_wrapper_is_removed() -> None:
    signals = _read('app/analytics/kubernetes/alerts/signals.py')
    anomalies = _read('app/analytics/kubernetes/alerts/anomalies.py')
    contracts = _read('app/analytics/kubernetes/alerts/contracts.py')

    assert 'def build_cluster_signal_overview' not in signals
    assert 'def build_anomalies' not in anomalies
    assert 'AlertClusterSignalComparisonRow' not in contracts
