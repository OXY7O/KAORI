from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_analytics_domain_is_metrics_backend_neutral() -> None:
    service = read('app/analytics/object_storage/service.py')
    runtime = read('app/analytics/object_storage/runtime.py')
    resolver = read('app/analytics/object_storage/sources/resolver.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    contracts = read('app/analytics/shared/metrics/contracts.py')

    assert 'MetricsSource' in runtime
    assert 'resolve_object_storage_metrics_source' in runtime
    assert 'PrometheusConsumer' not in service
    assert 'PrometheusError' not in service
    assert 'query_profiles.prometheus' not in service
    assert '_SOURCE_ADAPTERS' in resolver
    assert "metrics_provider='prometheus'" in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioPrometheusMetricsSource.supports' in resolver
    assert 'PrometheusConsumer.for_asset' in adapter
    assert "scope_type='object_storage_system'" in adapter
    assert 'retry_count=0' in adapter
    assert 'class MetricsSource(Protocol)' in contracts

    for token in ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3'):
        assert token not in service
        assert token not in runtime
        assert token not in contracts


def test_prometheus_payload_parsing_is_owned_by_adapter_not_domain_service() -> None:
    service = read('app/analytics/object_storage/service.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')

    assert '_vector_scalar' in adapter
    assert '_vector_by_label' in adapter
    assert '_matrix_points' in adapter
    assert "payload.get('data')" not in service
    assert not (ROOT / 'app/analytics/object_storage/parsing.py').exists()
    assert not (ROOT / 'app/analytics/object_storage/metrics.py').exists()


def test_object_storage_analytics_exposes_kubernetes_style_surface_set() -> None:
    routes = read('app/analytics/routes.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')

    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
    ):
        assert f"endpoint='{endpoint}'" in routes
        assert f'analytics.{endpoint}' in menu


def test_object_storage_alertmanager_is_optional_and_evidence_boundaries_are_explicit() -> None:
    service = read('app/analytics/object_storage/service.py')
    boundary = read('app/templates/analytics/object_storage/partials/_evidence_boundary.html')

    assert 'Alertmanager is optional for this release' in service
    assert 'Committed Inventory' in boundary
    assert 'Operational Time-Series' in boundary
    assert 'Lifecycle Correlation · Deferred' in boundary
    assert 'metrics_source.provider_label' in boundary


def test_metrics_source_transport_failure_is_request_fail_fast() -> None:
    runtime = read('app/analytics/object_storage/runtime.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')

    assert 'source_wide_failure' in runtime
    assert 'if self.source_wide_failure is not None' in runtime
    assert 'if exc.source_wide' in runtime
    assert 'retry_count=0' in adapter


def test_prometheus_transport_capability_ownership_is_provider_core() -> None:
    resolver = read('app/prometheus/resolver.py')

    assert 'def _available_technical_capabilities' in resolver
    assert 'provider_payload = instance.capabilities or {}' in resolver
    assert 'binding_payload = binding.validation_evidence or {}' in resolver
    assert 'observed = _available_technical_capabilities(binding, instance)' in resolver


def test_object_storage_metrics_readiness_is_validation_owned_and_provider_qualified() -> None:
    contracts = read('app/analytics/shared/metrics/contracts.py')
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    binding_profiles = read('app/integrations/prometheus/binding_profiles.py')
    binding_validation = read('app/integrations/prometheus/binding_validation.py')
    validator_registry = read('app/integrations/prometheus/binding_validators/__init__.py')
    object_storage_validator = read('app/integrations/prometheus/binding_validators/object_storage.py')
    audit = read('app/integrations/prometheus/query_profiles/object_storage_audit.py')
    readiness_template = read('app/templates/analytics/object_storage/partials/_metrics_readiness.html')

    assert 'class MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in adapter
    assert "profile_key='object-storage-metrics-v1'" in binding_profiles
    assert "validation_strategy='custom'" in binding_profiles
    assert "register_binding_validator('object_storage_system'" in validator_registry
    assert 'ObjectStoragePrometheusProfileAuditor' in object_storage_validator
    assert 'return system.minio_connection is not None' in object_storage_validator
    assert "'metrics_readiness': audit" in object_storage_validator
    assert '_VALIDATION_ADAPTERS' in object_storage_validator
    assert "asset_profile='minio-v2'" in object_storage_validator
    assert 'get_binding_validator(binding.asset_type)' in binding_validation
    assert "profile.profile_key == 'kubernetes-metrics-v1'" not in binding_validation
    assert 'class ObjectStoragePrometheusProfileAuditor' in audit
    assert 'self.client.series(metrics)' in audit
    assert 'self.client.query(definition.expression)' in audit
    assert 'Operational Metrics Readiness' in readiness_template
    assert 'Runtime reachability is evaluated separately' in readiness_template


def test_object_storage_query_profile_classifies_required_recommended_and_optional_evidence() -> None:
    profile = read('app/integrations/prometheus/query_profiles/object_storage_v1.py')
    types = read('app/integrations/prometheus/query_profiles/types.py')

    assert "QueryReadinessTier = Literal['required', 'recommended', 'optional']" in types
    assert "readiness_tier: QueryReadinessTier = 'required'" in types
    assert "readiness_tier='recommended'" in profile
    assert "readiness_tier='optional'" in profile
    assert 'minio_bucket_quota_total_bytes' in profile


def test_object_storage_analysis_semantics_are_provider_neutral_and_page_specific() -> None:
    analysis = read('app/analytics/object_storage/analysis.py')
    presentation = read('app/analytics/object_storage/presentation.py')
    service = read('app/analytics/object_storage/service.py')
    index = read('app/templates/analytics/object_storage/index.html')

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
    assert 'object_storage/partials/_overview_analysis.html' in index
    assert 'object_storage/partials/_capacity_analysis.html' in index
    assert 'object_storage/partials/_performance_analysis.html' in index
    assert 'object_storage/partials/_forecast_analysis.html' in index
    assert 'object_storage/partials/_top_consumers_analysis.html' in index
    assert 'object_storage/partials/_reconciliation.html' in index


def test_object_storage_analysis_distinguishes_operational_domains_and_provenance() -> None:
    overview = read('app/templates/analytics/object_storage/partials/_overview_analysis.html')
    capacity = read('app/templates/analytics/object_storage/partials/_capacity_analysis.html')
    performance = read('app/templates/analytics/object_storage/partials/_performance_analysis.html')
    forecast = read('app/templates/analytics/object_storage/partials/_forecast_analysis.html')
    consumers = read('app/templates/analytics/object_storage/partials/_top_consumers_analysis.html')
    reconciliation = read('app/templates/analytics/object_storage/partials/_reconciliation.html')
    bucket_table = read('app/templates/analytics/object_storage/partials/_bucket_table.html')

    assert 'Operational Health Summary' in overview
    assert 'Bucket Concentration' in overview
    assert 'Capacity Operating Boundary' in capacity
    assert 'Remaining Headroom' in capacity
    assert 'Request Operating Boundary' in performance
    assert 'Success Ratio' in performance
    assert 'Forecast Operating Boundary' in forecast
    assert 'Linear baseline' in forecast
    alerts = read('app/templates/analytics/object_storage/partials/_alerts.html')

    assert 'Top Consumer Snapshot' in consumers
    assert 'Critical Signals' in alerts
    assert 'Signal Reading' in alerts
    assert 'Lifecycle Boundary' in alerts
    assert 'Highest Error Rate' in consumers
    assert 'Inventory &amp; Operational Reconciliation' in reconciliation
    assert 'observation times differ' in reconciliation
    assert 'row.usage_source' in bucket_table
    assert 'Committed Inventory is used only as an explicit field-level fallback' in bucket_table


def test_object_storage_performance_chart_keeps_request_and_error_series_separate() -> None:
    trend = read('app/templates/analytics/object_storage/partials/_trend.html')
    javascript = read('app/static/js/analytics/object_storage.js')

    assert 'data-object-storage-secondary-trend-points' in trend
    assert 'Request & Error Trend' in trend
    assert 'secondaryByTimestamp' in javascript
    assert "isPerformance ? 'Request Rate' : 'Storage Usage'" in javascript
    assert "label: 'Error Rate'" in javascript


def test_kubernetes_navigation_uses_full_product_name_instead_of_k8s_abbreviation() -> None:
    menu_paths = (
        'app/templates/components/navigation/analytics_menu.html',
        'app/templates/components/navigation/inventory_menu.html',
        'app/templates/components/navigation/governance_menu.html',
        'app/templates/components/navigation/kubernetes_operations_menu.html',
        'app/templates/components/navigation/platform_operations_menu.html',
    )
    combined = '\n'.join(read(path) for path in menu_paths)

    assert 'K8s' not in combined
    assert 'Kubernetes Analytics' in combined
    assert 'Kubernetes Inventory' in combined
    assert 'Kubernetes Governance' in combined
    assert 'Kubernetes Operations' in combined
    assert 'Kubernetes Administration' in combined



def test_object_storage_analytics_uses_explicit_runtime_states_and_blocking() -> None:
    runtime = read('app/analytics/object_storage/runtime.py')
    dependencies = read('app/analytics/object_storage/dependencies.py')
    controls = read('app/templates/analytics/object_storage/partials/_controls.html')
    blocker = read('app/templates/analytics/object_storage/partials/_dependency_blocker.html')
    index = read('app/templates/analytics/object_storage/index.html')
    hero = read('app/templates/analytics/object_storage/partials/_hero.html')

    for status in (
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
        assert status in runtime or status in dependencies
    assert 'required_contract_ready' in runtime
    assert 'metrics_runtime_blocker' in runtime
    assert 'metrics_query_blocker' in runtime
    assert 'object-storage-analytics-refresh-indicator' in controls
    assert 'Object Storage Analytics Unavailable' in blocker
    assert 'Analysis controls and metric-derived results stay hidden' in blocker
    blocker_index = index.index('{% if dependency_blocker %}')
    else_index = index.index('{% else %}', blocker_index)
    controls_index = index.index('partials/_controls.html')
    assert blocker_index < else_index < controls_index
    assert 'metrics_source.detail' not in hero
    assert "'Current Gate'" in hero


def test_object_storage_bucket_records_use_shared_kaori_table_contract() -> None:
    routes = read('app/analytics/routes.py')
    table = read('app/templates/analytics/object_storage/partials/_bucket_table.html')
    pagination = read('app/templates/analytics/components/_record_pagination.html')
    table_service = read('app/analytics/object_storage/bucket_table.py')

    assert "endpoint='object_storage_bucket_table'" in routes
    assert 'components/table_primitives.html' in table
    assert 'components/table_label.html' in table
    assert 'components/loading_bar.html' in table
    assert 'analytics/components/_record_pagination.html' in table
    assert 'components/analytics/_table_label_primitives.html' not in table
    assert 'object-storage-bucket-table-loading-indicator' in table
    assert "default=5" in table_service
    assert "{5, 10, 25, 50}" in table_service
    assert 'Canonical Inventory-aligned full-page + HTMX pagination' in pagination


def test_object_storage_overview_prioritizes_operational_decision_surface() -> None:
    index = read('app/templates/analytics/object_storage/index.html')
    workspaces = read('app/templates/analytics/object_storage/partials/_overview_workspaces.html')

    summary = index.index('partials/_summary.html')
    posture = index.index('partials/_overview_analysis.html')
    trend = index.index('partials/_trend.html')
    consumers = index.index('partials/_bucket_table.html')
    workspaces_index = index.index('partials/_overview_workspaces.html')
    readiness = index.index('partials/_metrics_readiness.html')
    assert posture < summary < trend < workspaces_index < consumers < readiness
    assert 'Analysis Workspace Snapshot' in workspaces
    assert 'Capacity &amp; Usage' in workspaces
    assert 'Performance' in workspaces
    assert 'Top Consumers' in workspaces
    assert 'Forecast' in workspaces


def test_object_storage_consumer_profile_staleness_is_explicit_and_direct_cutover() -> None:
    adapter = read('app/analytics/object_storage/sources/minio_prometheus.py')
    migration = read('migrations/versions/20260814_object_storage_metrics_profile.py')

    assert 'Consumer Validation Stale' in adapter
    assert 'expected_profile' in adapter
    assert "'object-storage-metrics-v1'" in adapter
    assert 'minio-metrics-2024-v1' not in adapter
    assert "validation_profile = 'object-storage-metrics-v1'" in migration
    assert "validation_profile = 'minio-metrics-2024-v1'" in migration


def test_prometheus_full_validation_refreshes_enabled_consumer_bindings() -> None:
    validation_tasks = read('app/integrations/validation/tasks.py')
    integrations_readme = read('app/integrations/README.md')
    prometheus_readme = read('app/integrations/prometheus/README.md')

    assert "result_payload['binding_validation_summary'] = _refresh_provider_bindings(" in validation_tasks
    assert "IntegrationBinding.query.filter_by(" in validation_tasks
    assert "enabled=True" in validation_tasks
    assert "'binding.validate'" in validation_tasks
    assert 'Provider Full Validation does not implicitly validate consumer bindings.' not in integrations_readme
    assert 'Provider Full Validation refreshes every enabled consumer binding' in integrations_readme
    assert 'Full Validation refreshes enabled consumer bindings' in prometheus_readme


def test_object_storage_forecast_is_worker_materialized_on_forecasting_queue() -> None:
    service = read('app/analytics/object_storage/service.py')
    materialization = read('app/analytics/object_storage/materialization.py')
    task = read('app/analytics/object_storage/tasks.py')
    adapter = read('app/analytics/object_storage/job_adapter.py')
    definition = read('app/jobs/definitions/object_storage_forecast_refresh.py')
    registry = read('app/jobs/registry.py')
    config = read('app/config/default.py')
    materialization_template = read('app/templates/jobs/configuration/definitions/_materialization_job.html')
    index = read('app/templates/analytics/object_storage/index.html')
    worker_status = read('app/templates/analytics/object_storage/partials/_forecast_worker_status.html')

    assert 'linear_forecast' not in service
    assert 'ObjectStorageForecastSnapshot' in materialization
    assert "execution_mode='background'" in materialization
    assert 'materialize_object_storage_forecasts' in task
    assert 'dispatch_object_storage_forecast_materialization' in adapter
    assert "JOB_KEY = 'object_storage.forecast.materialize'" in definition
    assert "queue_name='forecasting'" in definition
    assert 'OBJECT_STORAGE_FORECAST_REFRESH_DEFINITION' in registry
    assert "'app.analytics.object_storage.tasks.materialize_object_storage_forecasts'" in config
    assert 'FORECASTING_CELERY_QUEUE' in config
    assert 'eligible_target_count' in materialization_template
    assert 'materialization_target_label' in materialization_template
    assert 'selected_job.eligible_cluster_count' not in materialization_template
    assert 'Forecast Worker Materialization' in worker_status
    assert 'forecast_materialization.usable' in index
    assert (ROOT / 'app/models/object_storage_analytics.py').exists()
    assert (ROOT / 'migrations/versions/20260814_object_storage_forecast_snapshots.py').exists()
