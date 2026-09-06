from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_dashboard_is_registered_and_visible_beside_kubernetes() -> None:
    bootstrap = read('app/bootstrap/blueprints.py')
    navigation = read('app/templates/components/navigation/dashboards_menu.html')
    breadcrumbs = read('app/common/navigation.py')
    release_registry = read('scripts/release_surface_registry.py')

    assert 'from app.storage.object_storage.dashboard.routes import object_storage_dashboard_bp' in bootstrap
    assert 'object_storage_dashboard_bp,' in bootstrap
    assert "url_for('object_storage_dashboard.index')" in navigation
    assert '>Object Storage</span>' in navigation
    assert "request.endpoint.startswith('object_storage_dashboard.')" in navigation
    assert "endpoint.startswith(('kubernetes_dashboard.', 'object_storage_dashboard.'))" in breadcrumbs
    assert "'object_storage_dashboard': 'Object Storage Operations'" in breadcrumbs
    assert 'BreadcrumbItem(dashboard_label)' in breadcrumbs
    assert "navigation_endpoints=('kubernetes_dashboard.index', 'object_storage_dashboard.index')" in release_registry
    assert "blueprint_vars=('kubernetes_dashboard_bp', 'object_storage_dashboard_bp')" in release_registry


def test_dashboard_route_and_service_are_snapshot_only() -> None:
    routes = read('app/storage/object_storage/dashboard/routes.py')
    service = read('app/storage/object_storage/dashboard/service.py')

    assert "url_prefix='/dashboards/object-storage'" in routes
    assert routes.count("@permission_required('dashboard.view')") == 2
    assert "DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}" in routes
    assert "'kpi_cards': 'storage/object_storage/dashboard/partials/_kpi_cards.html'" in routes
    assert "'overview': 'storage/object_storage/dashboard/partials/_overview.html'" in routes
    assert "'system_health': 'storage/object_storage/dashboard/partials/_system_health.html'" in routes
    assert "'capacity': 'storage/object_storage/dashboard/partials/_capacity.html'" in routes
    assert "'signals': 'storage/object_storage/dashboard/partials/_signals.html'" in routes
    assert "'reporting': 'storage/object_storage/dashboard/partials/_reporting.html'" in routes

    assert 'read_analytics_snapshot(' in service
    assert 'get_forecast_snapshot(' in service
    assert 'analytics_snapshot_state(' in service
    assert 'forecast_snapshot_state(' in service
    assert 'def _alerts(selected: ObjectStorageSystem | None)' in service
    assert "dashboard['alerts'] = _alerts(selected)" in service
    assert "status_reason = 'Inventory & analytics ready.'" in service
    assert 'Committed inventory and analytics evidence are available.' not in service
    assert 'ObjectStorageBucket' not in service
    for forbidden in (
        'source_setup(',
        'MetricsConsumer(',
        'resolve_object_storage_metrics_source(',
        '.scalar(',
        '.vector(',
        '.trend(',
        'load_alert_stream(',
    ):
        assert forbidden not in service


def test_dashboard_matches_kubernetes_operational_layout_concept() -> None:
    content = read('app/templates/storage/object_storage/dashboard/partials/_content.html')
    hero = read('app/templates/storage/object_storage/dashboard/partials/_hero.html')
    page_hero = read('app/templates/components/page_hero.html')
    signal_overview = read('app/templates/storage/object_storage/dashboard/partials/_signal_overview.html')
    kubernetes_content = read('app/templates/kubernetes/dashboard/partials/_content.html')

    for label in ('Operations Overview', 'Capacity & Demand', 'Signals & Actions', 'Reporting'):
        assert label in content
        assert label in kubernetes_content
    assert 'components/workspace_tabs.html' in content
    assert 'storage/object_storage/dashboard/partials/_hero.html' in content
    assert 'storage/object_storage/dashboard/partials/_signal_overview.html' in content
    assert (
        'hx-get="{{ url_for(\'object_storage_dashboard.section\', section=tab_key) }}?{{ dashboard_query }}"' in content
    )
    assert 'hx-trigger="revealed"' in content
    assert (
        "hx-get=\"{{ url_for('object_storage_dashboard.section', section='kpi_cards') }}?{{ dashboard_query }}\""
        in signal_overview
    )
    assert 'hx-trigger="load"' in signal_overview
    assert 'All Systems' in signal_overview
    assert 'page_hero.operational_dashboard(' in hero
    assert 'No live provider query on page load' in page_hero
    assert 'class="mt-5 space-y-5"' in content


def test_dashboard_sections_are_object_storage_specific_and_committed_evidence_owned() -> None:
    overview = read('app/templates/storage/object_storage/dashboard/partials/_overview.html')
    system_health = read('app/templates/storage/object_storage/dashboard/partials/_system_health.html')
    kubernetes_health = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')
    kubernetes_inventory = read('app/templates/kubernetes/dashboard/partials/_inventory_summary.html')
    kubernetes_freshness = read('app/templates/kubernetes/dashboard/partials/_data_freshness.html')
    capacity = read('app/templates/storage/object_storage/dashboard/partials/_capacity.html')
    forecast = read('app/templates/storage/object_storage/dashboard/partials/_forecast_risk.html')
    consumers = read('app/templates/storage/object_storage/dashboard/partials/_top_consumers.html')
    signals = read('app/templates/storage/object_storage/dashboard/partials/_signals.html')
    response = read('app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html')
    actions = read('app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html')
    reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting.html')
    reporting_summary = read('app/templates/storage/object_storage/dashboard/partials/_reporting_summary.html')
    reporting_guidance = read('app/templates/storage/object_storage/dashboard/partials/_reporting_guidance.html')

    assert 'System Health Summary' in system_health
    for token in ('Inventory Snapshot', 'Data Freshness'):
        assert token in overview
    assert 'Capacity Snapshot' in capacity
    assert 'Forecast & Growth Risk' in forecast
    assert 'Top Bucket Consumers' in consumers
    assert 'storage/object_storage/dashboard/partials/_alerts_summary.html' in signals
    assert 'Alert Interpretation & Response' in response
    assert 'Recommended Actions' in actions
    assert 'storage/object_storage/dashboard/partials/_reporting_summary.html' in reporting
    assert 'Reporting Summary' in reporting_summary
    assert 'Reporting Interpretation & Next Steps' in reporting_guidance

    assert 'storage/object_storage/dashboard/partials/_system_health.html' in overview
    for token in (
        'components/table.html',
        "table_ui.table_classes('min-w-[1040px]')",
        'Snapshot Sources',
        'Metrics Source',
        'Alert Signals',
    ):
        assert token in system_health
        assert token in kubernetes_health

    assert "body_classes='grid grid-cols-2 gap-3 p-5 sm:grid-cols-3'" in overview
    assert "body_classes='grid grid-cols-2 gap-3 p-5 sm:grid-cols-3'" in kubernetes_inventory
    assert "body_classes='grid gap-3 p-5 sm:grid-cols-2'" in overview
    assert "body_classes='grid gap-3 p-5 sm:grid-cols-2'" in kubernetes_freshness
    assert 'overflow-x-auto' in system_health
    assert 'overflow-x-auto' not in capacity
    assert 'overflow-x-auto' not in signals
    assert 'Empty Committed Inventory Detected' in overview
    assert "url_for('jobs.configuration', job_key='object_storage.inventory.sync')" in overview


def test_system_health_summary_matches_kubernetes_pagination_contract() -> None:
    routes = read('app/storage/object_storage/dashboard/routes.py')
    service = read('app/storage/object_storage/dashboard/service.py')
    content = read('app/templates/storage/object_storage/dashboard/partials/_content.html')
    health = read('app/templates/storage/object_storage/dashboard/partials/_system_health.html')
    kubernetes_health = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')

    assert 'SYSTEM_HEALTH_PAGE_SIZES = {5, 10, 25, 50}' in routes
    assert "request.args.get('system_health_page', '1')" in routes
    assert "request.args.get('system_health_per_page', '5')" in routes
    assert "'system_health': 'storage/object_storage/dashboard/partials/_system_health.html'" in routes
    assert 'from app.common.pagination import paginate_sequence' in service
    assert "'empty_observed_systems': len(empty_observed_systems)" in service
    assert "if section in {'overview', 'system_health'}:" in service
    assert "dashboard['system_health_pagination'] = pagination" in service
    assert "'&system_health_page=' ~ dashboard.system_health_pagination.page" in content
    assert "'&system_health_per_page=' ~ dashboard.system_health_pagination.per_page" in content

    for token in (
        'components/pagination.html',
        "id='object-storage-system-health-section'",
        'object-storage-system-health-loading',
        'system_health_page',
        'system_health_per_page',
        '>Rows<',
        'Previous',
        'Next',
        'pagination_ui.numeric_pages',
        'Showing {{ pagination.start_item }}–{{ pagination.end_item }} of {{ pagination.total_items }} Systems',
    ):
        assert token in health

    for size in ('5', '10', '25', '50'):
        assert size in health
    assert 'components/pagination.html' in kubernetes_health
    assert 'cluster_health_per_page' in kubernetes_health
    assert 'pagination_ui.numeric_pages' in kubernetes_health


def test_object_storage_analytics_verifier_tracks_current_snapshot_contract() -> None:
    verifier = read('scripts/verify_object_storage_analytics.py')

    assert "assert 'Operational Metrics Contract' in readiness" in verifier
    assert "assert 'Readiness By Evidence Domain' in readiness" in verifier
    assert "assert 'Object Storage → Metrics → Analytics Snapshot' in dependency_blocker" in verifier
    assert "assert 'readiness_step_count = 3' in hero_blocked" in verifier
    assert (
        "for label in ('Forecast Outlook', 'Usage Trend', 'Bucket Forecasts', 'Worker & Method', 'Evidence')"
        in verifier
    )


def test_capacity_dashboard_matches_kubernetes_forecast_and_top_consumer_pattern() -> None:
    capacity = read('app/templates/storage/object_storage/dashboard/partials/_capacity.html')
    forecast = read('app/templates/storage/object_storage/dashboard/partials/_forecast_risk.html')
    consumers = read('app/templates/storage/object_storage/dashboard/partials/_top_consumers.html')
    kubernetes_forecast = read('app/templates/kubernetes/dashboard/partials/_forecast_risk.html')
    kubernetes_consumers = read('app/templates/kubernetes/dashboard/partials/_top_consumers.html')
    service = read('app/storage/object_storage/dashboard/service.py')
    presentation = read('app/storage/object_storage/dashboard/presentation.py')

    assert 'storage/object_storage/dashboard/partials/_forecast_risk.html' in capacity
    assert 'storage/object_storage/dashboard/partials/_top_consumers.html' in capacity
    for token in (
        'components/operational_flow_steps.html',
        'Data Scope',
        'Overall Capacity Risk',
        'What This Means',
        'Recommended Action',
        'Recommended Capacity Action Flow',
    ):
        assert token in capacity
    for token in (
        'components/forecast_projection_chart.html',
        'Projected Storage Utilization Trend',
        'Historical usage is solid; the forward 30-day projection is dashed.',
        'Forecast Conclusion',
    ):
        assert token in forecast
    assert 'components/forecast_projection_chart.html' in kubernetes_forecast
    assert 'Projected Utilization Trend' in kubernetes_forecast
    for token in (
        'consumer_panel',
        'Storage Usage',
        'Request Activity',
        'Top 3',
        'Activity Gaps',
        'High Usage',
    ):
        assert token in consumers
    assert 'consumer_panel' in kubernetes_consumers
    assert 'build_forecast_view(payload, state)' in service
    assert "'chart_items': [chart_item] if chart_item else []" in presentation
    assert "'usage': usage_items" in presentation
    assert "'requests': request_items" in presentation


def test_signals_and_reporting_match_kubernetes_dashboard_composition() -> None:
    signals = read('app/templates/storage/object_storage/dashboard/partials/_signals.html')
    alerts = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')
    response = read('app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html')
    actions = read('app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html')
    reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting.html')
    reporting_summary = read('app/templates/storage/object_storage/dashboard/partials/_reporting_summary.html')
    reporting_guidance = read('app/templates/storage/object_storage/dashboard/partials/_reporting_guidance.html')
    kubernetes_signals = read('app/templates/kubernetes/dashboard/partials/_content.html')
    kubernetes_reporting = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    service = read('app/storage/object_storage/dashboard/service.py')

    for token in (
        'storage/object_storage/dashboard/partials/_alerts_summary.html',
        'storage/object_storage/dashboard/partials/_alert_response_guidance.html',
        'storage/object_storage/dashboard/partials/_recommended_actions.html',
    ):
        assert token in signals
    assert 'Alerts Summary' in alerts
    assert 'def _alerts(selected: ObjectStorageSystem | None)' in service
    assert "for case in posture['cases'][:3]" in service
    assert 'Alert Interpretation & Response' in response
    assert 'Controlled Response Flow' in response
    assert 'Recommended Actions' in actions
    assert 'dashboard-recommended-actions' in kubernetes_signals
    assert "dashboard['recommended_actions'] = _recommended_actions(selected)" in service
    assert 'get_dashboard_recommendation_findings' in service

    assert "peer_content_grid.column_classes('primary', 'seven-five')" in reporting
    assert "peer_content_grid.column_classes('secondary', 'seven-five')" in reporting
    assert 'Reporting Summary' in reporting_summary
    assert 'Recent Report Activity' in reporting_summary
    assert 'Reporting Interpretation & Next Steps' in reporting_guidance
    assert 'Reporting Control' in reporting_guidance
    assert 'Controlled Reporting Flow' in reporting_guidance
    assert 'Controlled Reporting Flow' in kubernetes_reporting
