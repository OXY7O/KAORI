import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_jinja_assignment(source: str, variable: str, value: str) -> bool:
    pattern = rf'{{%\s*set\s+{re.escape(variable)}\s*=\s*(["\']){re.escape(value)}\1\s*%}}'
    return re.search(pattern, source) is not None


def test_object_storage_analytics_domain_is_metrics_backend_neutral() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    runtime = read('app/storage/object_storage/analytics/runtime.py')
    resolver = read('app/storage/object_storage/analytics/sources/resolver.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    contracts = read('app/common/analytics/metrics/contracts.py')

    assert 'MetricsSource' in runtime
    assert 'resolve_object_storage_metrics_source' in runtime
    assert 'MetricsConsumer' not in service
    assert 'MetricsSourceError' not in service
    assert 'query_profiles.prometheus' not in service
    assert '_SOURCE_ADAPTERS' in resolver
    assert "asset_profile='minio-v2'" in resolver
    assert 'MinioMetricsSourceAdapter.supports' in resolver
    assert 'MetricsConsumer.for_asset' in adapter
    assert "scope_type='object_storage_system'" in adapter
    assert 'retry_count=0' in adapter
    assert 'class MetricsSource(Protocol)' in contracts

    for token in ('MinioClient', 'MinioInstance', 'secret_key', 'access_key', 'boto3'):
        assert token not in service
        assert token not in runtime
        assert token not in contracts


def test_metrics_adapter_payload_parsing_is_owned_by_adapter_not_domain_service() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')

    assert '_vector_scalar' in adapter
    assert '_vector_by_label' in adapter
    assert '_matrix_points' in adapter
    assert "payload.get('data')" not in service
    assert not (ROOT / 'app/storage/object_storage/analytics/parsing.py').exists()
    assert not (ROOT / 'app/storage/object_storage/analytics/metrics.py').exists()


def test_object_storage_analytics_exposes_kubernetes_style_surface_set() -> None:
    routes = read('app/analytics/routes.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')

    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_recommendations',
        'object_storage_alerts',
    ):
        assert f"endpoint='{endpoint}'" in routes
    for endpoint in (
        'object_storage_overview',
        'object_storage_capacity',
        'object_storage_performance',
        'object_storage_forecast',
        'object_storage_top_consumers',
        'object_storage_alerts',
    ):
        assert f'analytics.{endpoint}' in menu
    assert 'analytics.object_storage_recommendations' not in menu


def test_object_storage_analytics_uses_dedicated_rbac_and_sidebar_visibility() -> None:
    import yaml

    routes = read('app/storage/object_storage/analytics/routes.py')
    access = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    defaults = read('app/access/rbac/defaults.py')
    sidebar = read('app/templates/components/navigation/sidebar.html')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    migration = read('migrations/versions/20260814_object_storage_rbac_split.py')

    permissions = {item['key']: item for item in access['permissions']}
    object_storage_permission = permissions['object_storage_analytics.view']

    assert routes.count("@permission_required('object_storage_analytics.view')") == 10
    assert object_storage_permission['module'] == 'storage_analytics'
    assert "load_definition_document('access/rbac/access.yaml'" in defaults
    assert "has_permission('object_storage_analytics.view')" in sidebar
    assert '{% if can_object_storage_analytics %}' in menu
    assert '{% if can_kubernetes_analytics %}' in menu
    assert "'analytics.view'" in migration
    assert '_copy_role_assignments' in migration


def test_object_storage_alert_sources_are_alertmanager_first_with_metrics_source_fallback() -> None:
    source = read('app/storage/object_storage/analytics/alert_sources.py')
    boundary = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')

    assert "ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'metrics_source')" in source
    assert "required_capabilities=('alerts_v2',)" in source
    assert 'scope_type=_OBJECT_STORAGE_SCOPE' in source
    assert 'Metrics Source Fallback Active' in source
    assert 'ACTIVE_ALERTS_EXPRESSION' in source
    assert 'Automatic · Alertmanager Preferred' in controls
    assert 'Alert Lifecycle & Routing' in boundary
    assert 'Lifecycle Correlation · Deferred' not in boundary
    assert 'Committed Inventory' in boundary
    assert 'Operational Time-Series' in boundary
    assert 'metrics_source.provider_label' in boundary


def test_metrics_source_transport_failure_is_request_fail_fast() -> None:
    runtime = read('app/storage/object_storage/analytics/runtime.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')

    assert 'source_wide_failure' in runtime
    assert 'if self.source_wide_failure is not None' in runtime
    assert 'if exc.source_wide' in runtime
    assert 'retry_count=0' in adapter


def test_metrics_source_transport_capability_ownership_is_provider_core() -> None:
    resolver = read('app/integrations/observability/metrics_source/application/resolver.py')

    assert 'def _available_technical_capabilities' in resolver
    assert 'provider_payload = instance.capabilities or {}' in resolver
    assert 'binding_payload = binding.validation_evidence or {}' in resolver
    assert 'observed = _available_technical_capabilities(binding, instance)' in resolver


def test_object_storage_metrics_readiness_is_validation_owned_and_provider_qualified() -> None:
    contracts = read('app/common/analytics/metrics/contracts.py')
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    binding_profile_catalog = read('app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml')
    binding_validation = read('app/integrations/observability/metrics_source/binding_validation.py')
    validator_registry = read('app/integrations/observability/metrics_source/binding_validators/__init__.py')
    object_storage_validator = read(
        'app/integrations/observability/metrics_source/binding_validators/object_storage.py'
    )
    audit = read('app/integrations/observability/metrics_source/query_profiles/object_storage_audit.py')
    readiness_template = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')

    assert 'class MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in contracts
    assert 'def readiness(self) -> MetricsReadinessSnapshot' in adapter
    assert 'profile_key: object-storage-metrics-v1' in binding_profile_catalog
    assert 'validation_strategy: custom' in binding_profile_catalog
    assert "register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'object_storage_system'" in validator_registry
    assert 'ObjectStorageMetricsProfileAuditor' in object_storage_validator
    assert 'owner = object_storage_owner(system.id)' in object_storage_validator
    assert "owner.provider_key == 'minio'" in object_storage_validator
    assert "'metrics_readiness': audit" in object_storage_validator
    assert '_VALIDATION_ADAPTERS' in object_storage_validator
    assert "asset_profile='minio-v2'" in object_storage_validator
    assert 'get_binding_validator(instance.adapter_key, binding.asset_type)' in binding_validation
    assert "profile.profile_key == 'kubernetes-metrics-v1'" not in binding_validation
    assert 'class ObjectStorageMetricsProfileAuditor' in audit
    assert 'self.client.series(metrics)' in audit
    assert 'self.client.query(definition.expression)' in audit
    assert 'Operational Metrics Contract' in readiness_template
    assert 'Runtime reachability and samples are evaluated when the worker commits a snapshot.' in readiness_template


def test_object_storage_query_profile_classifies_required_recommended_and_optional_evidence() -> None:
    profile = read('app/integrations/observability/metrics_source/query_profiles/object_storage_v1.py')
    types = read('app/integrations/observability/metrics_source/query_profiles/types.py')

    assert "QueryReadinessTier = Literal['required', 'recommended', 'optional']" in types
    assert "readiness_tier: QueryReadinessTier = 'required'" in types
    assert "readiness_tier='recommended'" in profile
    assert "readiness_tier='optional'" in profile
    assert 'minio_bucket_quota_total_bytes' in profile


def test_object_storage_analysis_semantics_are_provider_neutral_and_page_specific() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')
    analysis = read('app/storage/object_storage/analytics/analysis.py')
    presentation = read('app/storage/object_storage/analytics/presentation.py')
    service = read('app/storage/object_storage/analytics/service.py')

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
    assert 'storage/object_storage/analytics/partials/_overview_analysis.html' in index
    assert 'storage/object_storage/analytics/partials/_overview_workspace.html' in index
    assert 'storage/object_storage/analytics/partials/_capacity_workspace.html' in index
    assert 'storage/object_storage/analytics/partials/_performance_workspace.html' in index
    assert 'storage/object_storage/analytics/partials/_forecast_workspace.html' in index
    assert 'storage/object_storage/analytics/partials/_top_consumers_workspace.html' in index
    assert 'storage/object_storage/analytics/partials/_alerts_workspace.html' in index
    capacity_workspace = read('app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html')
    assert 'storage/object_storage/analytics/partials/_reconciliation.html' in capacity_workspace


def test_object_storage_analysis_distinguishes_operational_domains_and_provenance() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_analysis.html')
    capacity = read('app/templates/storage/object_storage/analytics/partials/_capacity_analysis.html')
    performance = read('app/templates/storage/object_storage/analytics/partials/_performance_analysis.html')
    forecast = read('app/templates/storage/object_storage/analytics/partials/_forecast_analysis.html')
    consumer_storage = read('app/templates/storage/object_storage/analytics/partials/_top_consumers_storage.html')
    consumer_activity = read('app/templates/storage/object_storage/analytics/partials/_top_consumers_activity.html')
    reconciliation = read('app/templates/storage/object_storage/analytics/partials/_reconciliation.html')
    bucket_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')

    assert 'Operational Health Summary' in overview
    assert 'Bucket Concentration' in overview
    capacity_pressure = read('app/templates/storage/object_storage/analytics/partials/_capacity_pressure.html')

    assert 'Capacity Operating Boundary' in capacity
    assert 'Physical Capacity Utilization' in capacity
    assert 'Usage Direction' in capacity
    assert 'Remaining Headroom' in capacity
    assert 'Quota Pressure &amp; Usage Concentration' in capacity_pressure
    assert 'Quota Evidence Coverage' in capacity_pressure
    assert 'Critical Quota' in capacity_pressure
    performance_traffic = read('app/templates/storage/object_storage/analytics/partials/_performance_traffic.html')

    assert 'Request Path Operating Boundary' in performance
    assert 'Request Reliability' in performance
    assert 'Request Processing Pressure' in performance
    assert 'Success Ratio' in performance
    assert 'Throughput &amp; Request Direction' in performance_traffic
    assert 'Increasing demand is descriptive, not automatically unhealthy' in performance_traffic
    assert 'Bucket Request Path Records' in bucket_table
    assert 'row.request_source' in bucket_table
    assert 'row.error_source' in bucket_table
    assert "include_capacity_detail=page_key != 'performance'" in read(
        'app/storage/object_storage/analytics/service.py'
    )
    assert 'Forecast Operating Boundary' in forecast
    methodology = read('app/templates/storage/object_storage/analytics/partials/_forecast_methodology.html')
    assert 'Linear baseline' in methodology
    alerts_summary = read('app/templates/storage/object_storage/analytics/partials/_alerts_summary.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    alert_source_evidence = read('app/templates/storage/object_storage/analytics/partials/_alerts_source_evidence.html')

    assert 'Storage Consumer Leaders' in consumer_storage
    assert 'Request Activity Leaders' in consumer_activity
    assert 'Provider Alerts' in alerts_summary
    assert 'Anomaly Signals' in alerts_summary
    assert 'Alert Reading' in alerts_summary
    assert 'Provider alerts and anomaly signals are separate' in alerts_summary
    assert 'Provider Alert Records' in alert_records
    assert 'Metrics Source ALERTS provides narrower rule-state evidence.' in alert_records
    assert 'Alertmanager Authority' in alert_source_evidence
    assert 'Highest Error Ratio' in consumer_activity
    assert 'Inventory &amp; Operational Reconciliation' in reconciliation
    assert 'observation times differ' in reconciliation
    assert 'row.usage_source' in bucket_table
    assert 'Bucket Capacity Records' in bucket_table
    assert 'progress_bar.semantic_bar(row.quota_utilization' in bucket_table
    assert 'Inventory is an explicit field-level fallback where supported.' in bucket_table


def test_object_storage_performance_chart_keeps_request_and_error_series_separate() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    javascript = read('app/static/js/storage/object_storage/analytics.js')

    assert 'data-object-storage-secondary-trend-points' in trend
    assert 'Request &amp; Error Trend' in trend
    assert 'secondaryByTimestamp' in javascript
    assert "isPerformance ? 'Request Rate' : (isForecast ? 'Observed Usage' : 'Storage Usage')" in javascript
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
    index = read('app/templates/storage/object_storage/analytics/index.html')
    runtime = read('app/storage/object_storage/analytics/runtime.py')
    dependencies = read('app/storage/object_storage/analytics/dependencies.py')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    dependency_notice = read('app/templates/storage/object_storage/analytics/partials/_dependency_notice.html')
    hero = read('app/templates/storage/object_storage/analytics/partials/_hero.html')
    hero_blocked = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')

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
    assert "'inventory_required'" in dependencies
    service = read('app/storage/object_storage/analytics/service.py')
    assert service.count('inventory_required_blocker(system)') >= 1
    assert "return get_object_storage_analytics_context('alerts', query_args)" in service
    assert 'return get_object_storage_analytics_context(page_key, query_args)' in service
    assert 'object-storage-analytics-refresh-indicator' in controls
    shared_blocker = read('app/templates/components/dependencies/_blocker.html')
    assert 'components/dependencies/_blocker.html' in blocker
    assert 'Object Storage → Metrics → Analytics Snapshot' in blocker
    assert 'Alert Evidence' not in blocker
    assert blocker.count('dependency_grid_classes = "lg:grid-cols-3"') == 2
    assert 'Analytics Readiness' in shared_blocker
    assert 'Current Blocker' in shared_blocker
    assert 'dependency_route_summary' in shared_blocker
    assert 'dependency_step_count' in shared_blocker
    assert 'dependency_blocker.diagnostic_detail' in dependency_notice
    blocker_index = index.index('{% if dependency_blocker %}')
    else_index = index.index('{% else %}', blocker_index)
    controls_index = index.index('partials/_controls.html')
    assert blocker_index < else_index < controls_index
    assert 'metrics_source.detail' not in hero
    assert "'Current Step'" in hero_blocked
    assert "'Progress'" in hero_blocked
    assert "'Analytics Readiness'" in hero_blocked
    assert 'readiness_step_count = 3' in hero_blocked
    assert "3: 'Analytics Snapshot'" in hero_blocked
    assert has_jinja_assignment(hero_blocked, 'blocker_status', 'Capability Incomplete')


def test_object_storage_bucket_records_use_shared_kaori_table_contract() -> None:
    routes = read('app/analytics/routes.py')
    table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    pagination = read('app/templates/analytics/components/_record_pagination.html')
    table_service = read('app/storage/object_storage/analytics/bucket_table.py')

    assert "endpoint='object_storage_bucket_table'" in routes
    assert 'components/table_primitives.html' in table
    assert 'components/table_label.html' in table
    assert 'components/loading_bar.html' in table
    assert 'analytics/components/_record_pagination.html' in table
    assert 'components/analytics/_table_label_primitives.html' not in table
    assert 'object-storage-bucket-table-loading-indicator' in table
    assert 'default=5' in table_service
    assert "'overview': 'consumers'" not in table_service
    assert "'capacity': 'quota'" in table_service
    assert "'performance': 'buckets'" in table_service
    assert "'top_consumers': 'records'" in table_service
    assert '{5, 10, 25, 50}' in table_service
    assert 'Canonical Inventory-aligned full-page + HTMX pagination' in pagination
    assert 'clear_filters_action' in table
    assert 'data-lucide="x"' in read('app/templates/components/table_registry.html')
    assert 'Bucket Consumption Evidence' not in table


def test_object_storage_overview_matches_kubernetes_overview_hero_and_tab_contract() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')
    service = read('app/storage/object_storage/analytics/service.py')
    pages = read('app/storage/object_storage/analytics/pages.py')
    hero = read('app/templates/storage/object_storage/analytics/partials/_hero.html')
    hero_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_posture.html')
    hero_blocked = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    layout = read('app/templates/layouts/app.html')

    assert "'Analytics Overview'" in pages
    assert 'partials/_hero_posture.html' in hero
    assert 'partials/_hero_blocked_posture.html' in hero
    assert "'Operational Posture'" in hero_posture
    assert "'Analytics Status'" in hero_posture
    assert "'Capacity Use'" in hero_posture
    assert "'Error Ratio'" in hero_posture
    assert "'Analytics Readiness'" in hero_blocked
    assert "'Current Step'" in hero_blocked
    assert "'Progress'" in hero_blocked
    assert "'Analytics Readiness'" in hero_blocked
    assert 'readiness_step_count = 3' in hero_blocked
    assert "3: 'Analytics Snapshot'" in hero_blocked
    assert has_jinja_assignment(hero_blocked, 'blocker_status', 'Capability Incomplete')

    assert 'components/content_tabs.html' in workspace
    assert 'data-analytics-tabset' in workspace
    assert 'data-analytics-tabset-id="object-storage-overview-content"' in workspace
    assert 'data-analytics-preserve-tab' in read(
        'app/templates/storage/object_storage/analytics/partials/_controls.html'
    )
    for label in ('Capacity', 'Performance', 'Consumers', 'Forecast', 'Evidence'):
        assert f"'{label}'" in workspace
    for partial in (
        '_overview_capacity_snapshot.html',
        '_overview_performance_snapshot.html',
        '_overview_consumer_snapshot.html',
        '_overview_forecast_snapshot.html',
        '_reconciliation.html',
        '_metrics_readiness.html',
        '_evidence_boundary.html',
    ):
        assert partial in workspace

    assert 'Consumer Concentration Snapshot' in read(
        'app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html'
    )
    assert '_bucket_table.html' not in workspace

    controls_index = index.index('partials/_controls.html')
    health_index = index.index('partials/_overview_analysis.html')
    workspace_index = index.index('partials/_overview_workspace.html')
    assert controls_index < health_index < workspace_index
    assert 'partials/_overview_workspaces.html' not in index
    assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials/_overview_workspaces.html').exists()

    assert 'js/analytics/controls.js' in layout
    assert 'js/kubernetes/analytics/controls.js' not in layout
    assert (ROOT / 'app/static/js/analytics/controls.js').exists()
    assert not (ROOT / 'app/static/js/kubernetes/analytics/controls.js').exists()


def test_object_storage_capacity_and_performance_match_shared_analytics_hero_and_tab_contract() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')
    service = read('app/storage/object_storage/analytics/service.py')
    pages = read('app/storage/object_storage/analytics/pages.py')
    hero_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_posture.html')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    capacity_workspace = read('app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html')
    performance_workspace = read('app/templates/storage/object_storage/analytics/partials/_performance_workspace.html')
    table_service = read('app/storage/object_storage/analytics/bucket_table.py')
    javascript = read('app/static/js/storage/object_storage/analytics.js')

    assert "'Object Storage Capacity & Usage'" in pages
    assert "'Object Storage Performance'" in pages
    assert "'Capacity Posture'" in hero_posture
    assert "'Capacity Status'" in hero_posture
    assert "'Performance Posture'" in hero_posture
    assert "'Request Health'" in hero_posture
    assert "'Utilization'" in hero_posture
    assert "'Headroom'" in hero_posture
    assert "'Request Rate'" in hero_posture

    assert 'partials/_capacity_workspace.html' in index
    assert 'partials/_performance_workspace.html' in index
    assert 'data-analytics-tabset-id="object-storage-capacity-content"' in capacity_workspace
    assert 'data-analytics-tabset-id="object-storage-performance-content"' in performance_workspace
    for label in ('Summary', 'Usage Trend', 'Quota & Buckets', 'Evidence'):
        assert f"'{label}'" in capacity_workspace
    for label in ('Request Health', 'Traffic & Trend', 'Bucket Activity', 'Evidence'):
        assert f"'{label}'" in performance_workspace

    assert 'data-analytics-preserve-tab' in controls
    assert 'Automatic · Alertmanager Preferred' in controls
    assert "'capacity': 'quota'" in table_service
    assert "'performance': 'buckets'" in table_service
    assert "'top_consumers': 'records'" in table_service
    assert "document.addEventListener('kaori:analytics-tab-visible'" in javascript


def test_object_storage_forecast_consumers_and_alerts_use_shared_tab_workspace_contract() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')
    hero_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_posture.html')
    forecast_workspace = read('app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html')
    forecast_methodology = read('app/templates/storage/object_storage/analytics/partials/_forecast_methodology.html')
    consumer_workspace = read('app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html')
    alerts_workspace = read('app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    alert_source_evidence = read('app/templates/storage/object_storage/analytics/partials/_alerts_source_evidence.html')

    assert 'partials/_forecast_workspace.html' in index
    assert 'partials/_top_consumers_workspace.html' in index
    assert 'partials/_alerts_workspace.html' in index

    assert 'data-analytics-tabset-id="object-storage-forecast-content"' in forecast_workspace
    for label in ('Forecast Outlook', 'Usage Trend', 'Bucket Forecasts', 'Worker & Method', 'Evidence'):
        assert f"'{label}'" in forecast_workspace
    assert 'Linear baseline · planning signal only' in forecast_methodology
    assert "'Forecast Posture'" in hero_posture
    assert "'Forecast Outlook'" in hero_posture

    assert 'data-analytics-tabset-id="object-storage-top-consumers-content"' in consumer_workspace
    for label in ('Storage Leaders', 'Request Activity', 'Consumer Records', 'Evidence'):
        assert f"'{label}'" in consumer_workspace
    assert "'Consumer Posture'" in hero_posture
    assert "'Usage Concentration'" in hero_posture

    assert 'data-analytics-tabset-id="object-storage-alerts-content"' in alerts_workspace
    for label in ('Alert Overview', 'Provider Alerts', 'Anomaly Signals', 'Recommendations', 'Evidence'):
        assert f"'{label}'" in alerts_workspace
    assert "'Alert Posture'" in hero_posture
    assert "'Active Alert State'" in hero_posture
    assert '_alert_records.html' in alerts_workspace
    assert '_alerts_source_evidence.html' in alerts_workspace
    assert 'clear_filters_action' in alert_records
    assert 'Metrics Source Fallback' in alert_source_evidence
    assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials/_alerts_lifecycle.html').exists()

    for retired in ('_summary.html', '_top_consumers_analysis.html', '_alerts.html'):
        assert not (ROOT / 'app/templates/storage/object_storage/analytics/partials' / retired).exists()


def test_object_storage_consumer_profile_staleness_is_explicit_and_direct_cutover() -> None:
    adapter = read('app/storage/object_storage/analytics/sources/providers/minio/metrics.py')
    migration = read('migrations/versions/20260814_object_storage_metrics_profile.py')

    assert 'Consumer Validation Stale' in adapter
    assert 'expected_profile' in adapter
    assert "'object-storage-metrics-v1'" in adapter
    assert 'minio-metrics-2024-v1' not in adapter
    assert "validation_profile = 'object-storage-metrics-v1'" in migration
    assert "validation_profile = 'minio-metrics-2024-v1'" in migration


def test_metrics_source_full_validation_keeps_consumer_bindings_independent() -> None:
    validation_tasks = read('app/integrations/validation/tasks.py')
    integrations_readme = read('app/integrations/README.md')
    metrics_source_readme = read('app/integrations/observability/metrics_source/README.md')

    full_validation = validation_tasks.split('def validate_integration_instance', 1)[1].split(
        'def _as_result_payload', 1
    )[0]
    assert '_refresh_provider_bindings(' not in full_validation
    assert 'binding_validation_summary' not in full_validation
    assert 'Provider Full Validation is intentionally provider-core only' in integrations_readme
    assert 'only the explicit binding `Validate` action rebuilds consumer-specific evidence' in integrations_readme
    assert 'Full Validation is provider-core only' in metrics_source_readme
    assert 'explicit binding Validate action' in metrics_source_readme


def test_object_storage_forecast_is_worker_materialized_on_forecasting_queue() -> None:
    import yaml

    service = read('app/storage/object_storage/analytics/service.py')
    materialization = read('app/storage/object_storage/analytics/materialization.py')
    task = read('app/storage/object_storage/analytics/tasks.py')
    adapter = read('app/storage/object_storage/analytics/job_adapter.py')
    definition = read('app/platform_operations/jobs/definitions/object_storage_forecast_refresh.py')
    jobs = yaml.safe_load(read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml'))
    registry = read('app/platform_operations/jobs/registry.py')
    config = read('app/config/default.py')
    materialization_template = read(
        'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html'
    )
    worker_status = read('app/templates/storage/object_storage/analytics/partials/_forecast_worker_status.html')

    job = next(item for item in jobs['jobs'] if item['key'] == 'object_storage.forecast.materialize')

    assert 'linear_forecast' not in service
    assert 'ObjectStorageForecastSnapshot' in materialization
    assert "execution_mode='background'" in materialization
    assert 'materialize_object_storage_forecasts' in task
    assert 'dispatch_object_storage_forecast_materialization' in adapter
    assert "get_job_definition('object_storage.forecast.materialize')" in definition
    assert job['queue_name'] == 'forecasting'
    assert job['workload_class'] == 'forecasting'
    assert (
        job['dispatcher_path']
        == 'app.storage.object_storage.analytics.job_adapter:dispatch_object_storage_forecast_materialization'
    )
    assert '_JOB_DEFINITIONS: tuple[JobDefinition, ...] = load_job_definitions()' in registry
    assert "'app.storage.object_storage.analytics.tasks.materialize_object_storage_forecasts'" in config
    assert 'FORECASTING_CELERY_QUEUE' in config
    assert 'eligible_target_count' in materialization_template
    assert 'materialization_target_label' in materialization_template
    assert 'selected_job.eligible_cluster_count' not in materialization_template
    assert 'Forecast Worker Refresh' in worker_status
    forecast_workspace = read('app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html')
    assert 'forecast_materialization.usable' in forecast_workspace
    assert (ROOT / 'app/models/object_storage_analytics.py').exists()
    assert (ROOT / 'migrations/versions/20260814_object_storage_forecast_snapshots.py').exists()
    object_storage_jobs = [item for item in jobs['jobs'] if item.get('domain') == 'Object Storage Analytics']
    assert [item['key'] for item in object_storage_jobs] == [
        'object_storage.analytics.materialize',
        'object_storage.forecast.materialize',
    ]
    assert job['name'] == 'Object Storage Forecast Data Refresh'
    assert job['configuration_template'] == 'platform_operations/jobs/configuration/definitions/forecast_refresh.html'
    assert 'Snapshot Refresh Policy' in materialization_template
    assert 'Automatic Snapshot Refresh' in materialization_template

    forecast_config = read('app/templates/platform_operations/jobs/configuration/definitions/forecast_refresh.html')
    analytics_readme = read('app/storage/object_storage/analytics/README.md')
    assert "definition.domain == 'Object Storage Analytics'" in forecast_config
    assert "'Object Storage' if definition.domain == 'Object Storage Analytics' else 'Kubernetes'" in forecast_config
    assert 'history windows prepared by the' in forecast_config
    assert 'forecast worker.' in forecast_config
    assert '`object_storage.analytics.materialize` collects reusable operational metrics' in analytics_readme
    assert '`ObjectStorageAnalyticsSnapshot`' in analytics_readme
    assert 'Interactive page requests never query Metrics Source or Alertmanager' in analytics_readme


def test_object_storage_alerts_use_independent_alert_and_metric_evidence_paths() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    sources = read('app/storage/object_storage/analytics/alert_sources.py')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    evidence = read('app/templates/storage/object_storage/analytics/partials/_alerts_source_evidence.html')
    migration = read('migrations/versions/20260814_object_storage_alert_profile.py')

    assert "ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'metrics_source')" in sources
    assert "selected_source == 'alertmanager'" in sources
    assert "selected_source == 'metrics_source'" in sources
    assert "alertmanager = _load_alertmanager(system, selected_source='auto')" in sources
    assert "metrics_source = _load_metrics_source(system, selected_source='auto')" in sources
    assert 'Metrics Source Fallback Active' in sources
    assert 'Consumer Validation Stale' in sources
    assert "context['alerts_evidence_available']" in service
    assert "context['alerts_degraded']" in service
    assert 'Automatic · Alertmanager Preferred' in controls
    assert 'Alertmanager Lifecycle' in controls
    assert 'Metrics Snapshot Source' in controls
    assert 'Analytics Worker Snapshot' in controls
    assert 'Metrics Only' in records
    assert 'Silenced' in records
    assert 'Inhibited' in records
    assert 'Alertmanager Authority' in evidence
    assert 'Metrics Source Fallback' in evidence
    assert "validation_profile = 'object-storage-alerts-v1'" in migration
    assert "validation_status = 'validation_required'" in migration
