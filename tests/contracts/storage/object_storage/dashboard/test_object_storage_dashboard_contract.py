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
    assert "elif endpoint.startswith('kubernetes_dashboard.'):" in breadcrumbs
    assert "elif endpoint.startswith('object_storage_dashboard.'):" in breadcrumbs
    assert "BreadcrumbItem('Object Storage', 'database')" in breadcrumbs
    assert "BreadcrumbItem('Overview')" in breadcrumbs
    assert "navigation_endpoints=('kubernetes_dashboard.index', 'object_storage_dashboard.index')" in release_registry
    assert "blueprint_vars=('kubernetes_dashboard_bp', 'object_storage_dashboard_bp')" in release_registry


def test_dashboard_route_and_service_are_snapshot_only() -> None:
    routes = read('app/storage/object_storage/dashboard/routes.py')
    service = read('app/storage/object_storage/dashboard/service.py')

    assert "url_prefix='/dashboards/object-storage'" in routes
    assert routes.count("@permission_required('dashboard.view')") == 2
    assert 'normalize_operational_tab' in routes
    assert 'normalize_dashboard_page_size' in routes
    assert 'is_htmx_request(request.headers)' in routes
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

    framework = read('app/templates/components/operational_dashboard_workspace.html')

    for label in ('Operations Overview', 'Capacity & Demand', 'Signals & Actions', 'Reporting'):
        assert label in framework
    assert 'components/operational_dashboard_workspace.html' in content
    assert 'components/operational_dashboard_workspace.html' in kubernetes_content
    assert 'dashboard_workspace.controller(' in content
    assert 'dashboard_workspace.navigation(' in content
    assert 'dashboard_workspace.panel(' in content
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
    assert 'data-kaori-dashboard-framework="operational-v1"' in framework
    assert 'workspace_tabs.render(standard_tabs' in framework


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
    assert 'components/operational_alert_response.html' in response
    assert 'components/operational_recommendation_cards.html' in actions
    assert 'storage/object_storage/dashboard/partials/_reporting_summary.html' in reporting
    assert 'reporting_workspace.summary(' in reporting_summary
    assert 'reporting_workspace.guidance(' in reporting_guidance

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

    application_contract = read('app/dashboards/common/operational.py')
    pagination = read('app/common/pagination.py')
    assert 'DASHBOARD_PAGE_SIZES = PER_PAGE_OPTIONS' in application_contract
    assert 'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)' in pagination
    assert "request.args.get('system_health_page', '1')" in routes
    assert "normalize_dashboard_page_size(request.args.get('system_health_per_page'))" in routes
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

    assert 'for size in pagination.allowed_per_page' in health
    assert '[5, 10, 25, 50]' not in health
    assert 'components/pagination.html' in kubernetes_health
    assert 'cluster_health_per_page' in kubernetes_health
    assert 'pagination_ui.numeric_pages' in kubernetes_health


def test_object_storage_analytics_verifier_tracks_current_snapshot_contract() -> None:
    verifier = read('scripts/verify_object_storage_analytics.py')

    assert "assert 'Operational Metrics Contract' in readiness" in verifier
    assert "assert 'Readiness By Evidence Domain' in readiness" in verifier
    assert (
        "assert 'Object Storage → Metrics Source → Alert Source → Analytics Snapshot' in dependency_blocker" in verifier
    )
    assert "assert 'dependency_blocked_step = 4' in dependency_blocker" in verifier
    assert "assert 'page_hero.blocked_context_body(' in hero_blocked" in verifier
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
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    shared_alerts = read('app/templates/components/operational_alert_summary.html')
    shared_response = read('app/templates/components/operational_alert_response.html')
    shared_recommendations = read('app/templates/components/operational_recommendation_cards.html')
    kubernetes_signals = read('app/templates/kubernetes/dashboard/partials/_signals.html')
    kubernetes_actions = read('app/templates/kubernetes/dashboard/partials/_recommended_actions.html')
    kubernetes_reporting = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    service = read('app/storage/object_storage/dashboard/service.py')

    for token in (
        'storage/object_storage/dashboard/partials/_alerts_summary.html',
        'storage/object_storage/dashboard/partials/_alert_response_guidance.html',
        'storage/object_storage/dashboard/partials/_recommended_actions.html',
    ):
        assert token in signals
    assert 'components/operational_alert_summary.html' in alerts
    assert 'Alerts Summary' in shared_alerts
    assert 'def _alerts(selected: ObjectStorageSystem | None)' in service
    assert "for case in posture['cases'][:5]" in service
    assert 'components/operational_alert_response.html' in response
    assert 'Alert Interpretation & Response' in shared_response
    assert 'Controlled Response Flow' in shared_response
    assert 'components/numbered_governance_steps.html' in shared_response
    assert 'components/operational_flow_steps.html' not in response
    assert 'components/operational_recommendation_cards.html' in actions
    assert 'Recommended Actions' in shared_recommendations
    assert 'kubernetes/dashboard/partials/_recommended_actions.html' in kubernetes_signals
    assert 'dashboard-recommended-actions' in kubernetes_actions
    assert "dashboard['recommended_actions'] = _recommended_actions(selected)" in service
    assert 'get_dashboard_recommendation_findings' in service

    assert "peer_content_grid.column_classes('primary', 'seven-five')" in reporting
    assert "peer_content_grid.column_classes('secondary', 'seven-five')" in reporting
    assert 'components/reporting_dashboard_workspace.html' in reporting_summary
    assert 'reporting_workspace.summary(' in reporting_summary
    assert "'Object Storage'" in reporting_summary
    assert 'components/reporting_dashboard_workspace.html' in reporting_guidance
    assert 'reporting_workspace.guidance(' in reporting_guidance
    assert 'recent = reports_query.order_by(Report.created_at.desc()).limit(4).all()' in service
    assert 'Reporting Summary' in reporting_workspace
    assert 'Recent Report Activity' in reporting_workspace
    assert 'Reporting Workflow' in reporting_workspace
    assert 'Scope Bound' in reporting_workspace
    assert 'Evidence Backed' in reporting_workspace
    assert 'Review First' in reporting_workspace
    assert 'Governed Flow' in reporting_workspace
    assert 'Execution Mode' in reporting_workspace
    assert 'Reporting Tip' in reporting_workspace
    assert 'Use templates for repeatable report structure.' in reporting_workspace
    assert 'components/numbered_governance_steps.html' not in reporting_workspace
    assert 'components/operational_flow_steps.html' not in reporting_workspace
    assert 'components/reporting_dashboard_workspace.html' in kubernetes_reporting
    assert 'reporting_workspace.guidance(' in kubernetes_reporting


def test_object_storage_dashboard_uses_fast_shell_without_rebuilding_overview_per_section() -> None:
    service = read('app/storage/object_storage/dashboard/service.py')

    assert 'def _dashboard_shell_context(' in service
    overview = service.split('def get_dashboard_overview(', 1)[1].split('def get_dashboard_section(', 1)[0]
    section = service.split('def get_dashboard_section(', 1)[1]

    assert '_inventory_summary(' not in overview
    assert 'return _dashboard_shell_context(' in overview
    assert 'dashboard = get_dashboard_overview(' not in section
    assert 'dashboard = _dashboard_shell_context(' in section

    assert "if section in {'overview', 'system_health'}:" in section
    assert "elif section == 'kpi_cards':" in section
    assert "elif section == 'capacity':" in section
    assert "elif section == 'signals':" in section
    assert "elif section == 'reporting':" in section

    signals_branch = section.split("elif section == 'signals':", 1)[1].split("elif section == 'reporting':", 1)[0]
    assert '_forecast(selected)' not in signals_branch
    assert '_capacity(selected)' not in signals_branch
    assert '_top_consumers(selected)' not in signals_branch

    reporting_branch = section.split("elif section == 'reporting':", 1)[1]
    assert '_freshness(selected, systems)' not in reporting_branch

def test_fleet_freshness_renders_four_distinct_committed_evidence_types(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.storage.object_storage.dashboard import service

    systems = [
        SimpleNamespace(id=1, inventory_observed_at=datetime.now(UTC)),
        SimpleNamespace(id=2, inventory_observed_at=datetime.now(UTC)),
    ]
    analytics = {'1': True, '2': True}
    forecasts = {'1': True, '2': False}
    streams = {
        '1': {'connected': True, 'fallback_used': True},
        '2': {'connected': False, 'fallback_used': False},
    }

    def snapshot(system):
        key = str(system.id)
        return {'stream': streams[key]}, {'usable': analytics[key]}

    def get_forecast_snapshot(*, system_id: str, history_window: str):
        assert history_window == '30d'
        return {'usable': forecasts[system_id]}

    monkeypatch.setattr(service, '_snapshot_payload', snapshot)
    monkeypatch.setattr(service, 'get_forecast_snapshot', get_forecast_snapshot)
    monkeypatch.setattr(service, 'forecast_snapshot_state', lambda snapshot: snapshot)
    monkeypatch.setattr(service, '_alert_view', lambda payload: (payload['stream'], {}))

    rows = service._freshness(None, systems)
    assert [row['label'] for row in rows] == [
        'Inventory Fleet',
        'Analytics Fleet',
        'Forecast Fleet',
        'Alert Evidence Fleet',
    ]
    assert [row['status'] for row in rows] == ['Available', 'Ready', 'Partial', 'Partial']
    assert rows[1]['value'] == '2 / 2 systems'
    assert rows[2]['value'] == '1 / 2 systems'
    assert rows[3]['value'] == '1 / 2 systems'
    assert rows[3]['tone'] == 'warning'
    assert '1 system(s) using fallback evidence' in rows[3]['description']


def test_fleet_freshness_keeps_missing_and_fallback_evidence_explicit(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.storage.object_storage.dashboard import service

    systems = [SimpleNamespace(id=1, inventory_observed_at=None)]
    snapshot = {'stream': {'connected': True, 'fallback_used': True}}
    monkeypatch.setattr(service, '_snapshot_payload', lambda system: (snapshot, {'usable': True}))
    monkeypatch.setattr(service, '_alert_view', lambda payload: (payload['stream'], {}))
    monkeypatch.setattr(service, 'get_forecast_snapshot', lambda **kwargs: {'usable': False})
    monkeypatch.setattr(service, 'forecast_snapshot_state', lambda value: value)

    rows = service._freshness(None, systems)
    assert len(rows) == 4
    assert [row['status'] for row in rows] == [
        'Not Collected',
        'Ready',
        'Required',
        'Fallback',
    ]
    assert rows[3]['tone'] == 'warning'

    monkeypatch.setattr(service, '_snapshot_payload', lambda system: (None, {'usable': False}))
    rows = service._freshness(None, systems)
    assert len(rows) == 4
    assert [row['status'] for row in rows] == [
        'Not Collected',
        'Required',
        'Required',
        'Required',
    ]
    assert rows[3]['value'] == '0 / 1 systems'
    assert rows[3]['tone'] == 'unknown'


def test_object_storage_fleet_and_single_system_share_four_tile_renderer() -> None:
    source = read('app/storage/object_storage/dashboard/service.py')
    overview = read('app/templates/storage/object_storage/dashboard/partials/_overview.html')
    tile = read('app/templates/components/operational_evidence_tile.html')

    fleet_branch = source.split('def _freshness(', 1)[1].split('    analytics_snapshot = ', 1)[0]
    selected_branch = source.split('    analytics_snapshot = ', 1)[1].split('def _capacity(', 1)[0]
    assert fleet_branch.count("'label':") == 4
    assert selected_branch.count("'label':") == 4
    assert 'forecast_snapshot_state(' in fleet_branch
    assert '_snapshot_payload(system)' in fleet_branch
    assert '_alert_view(payload)' in fleet_branch
    assert "'Fallback' if alert_fallback else 'Available'" in fleet_branch
    assert "for item in dashboard.freshness" in overview
    assert 'evidence_tile.freshness(' in overview
    assert "body_classes='grid gap-3 p-5 sm:grid-cols-2'" in overview
    assert '{% macro freshness(' in tile


def test_system_health_alert_signals_reflect_committed_snapshot_source(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.storage.object_storage.dashboard import service

    system = SimpleNamespace(
        id='system-1',
        name='Storage One',
        environment='uat',
        status='connected',
        inventory_observed_at=datetime.now(UTC),
        buckets=[],
    )
    # Alert Intelligence cases are independent of provider alert snapshot availability.
    monkeypatch.setattr(
        service,
        '_kaori_alert_posture',
        lambda _system: {'total': 0, 'critical': 0, 'warning': 0, 'info': 0},
    )
    alertmanager_payload = {
        'alert_streams': {
            'alertmanager': {
                'connected': True,
                'resolved_source': 'alertmanager',
                'rows': [],
            },
        },
    }
    metrics_fallback_payload = {
        'alert_streams': {
            'alertmanager': {'connected': False, 'configured': True},
            'metrics_source': {
                'connected': True,
                'resolved_source': 'metrics_source',
                'rows': [],
            },
        },
    }
    cases = [
        (
            alertmanager_payload,
            {'usable': True, 'label': 'Ready'},
            True,
            False,
            'Alertmanager · committed alert evidence',
        ),
        (
            metrics_fallback_payload,
            {'usable': True, 'label': 'Ready'},
            True,
            True,
            'Metrics Source fallback · committed alert evidence',
        ),
        (
            {'alert_streams': {}},
            {'usable': True, 'label': 'Ready'},
            False,
            False,
            'No usable committed alert evidence',
        ),
        (
            None,
            {'usable': False, 'label': 'Required'},
            False,
            False,
            'No usable committed alert evidence',
        ),
        (
            alertmanager_payload,
            {'usable': False, 'label': 'Expired'},
            False,
            False,
            'No usable committed alert evidence',
        ),
    ]
    for payload, state, connected, fallback, label in cases:
        monkeypatch.setattr(service, '_snapshot_payload', lambda _system, result=(payload, state): result)
        rows = service._health_rows([system])
        assert len(rows) == 1
        row = rows[0]
        assert row['alerts_connected'] is connected
        assert row['alerts_fallback'] is fallback
        assert row['alert_source_label'] == label
        assert row['active_alerts'] == 0
        assert row['inventory_ready'] is True
        assert row['snapshot_ready'] is bool(state['usable'])


def test_object_storage_alert_source_indicator_uses_validated_row_fields_and_tones() -> None:
    service = read('app/storage/object_storage/dashboard/service.py')
    health = read('app/templates/storage/object_storage/dashboard/partials/_system_health.html')
    freshness = read('app/templates/storage/object_storage/dashboard/partials/_overview.html')
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')
    registry = read('app/templates/artifact_registry/partials/_overview_provider_health.html')
    application = read('app/dashboards/common/operational.py')
    storage_routes = read('app/storage/object_storage/dashboard/routes.py')
    registry_routes = read('app/artifact_registry/routes.py')
    kubernetes_routes = read('app/kubernetes/dashboard/routes.py')

    rows = service.split('def _health_rows(', 1)[1].split('def _dashboard_kpis(', 1)[0]
    for field in (
        "'inventory_ready':",
        "'snapshot_ready':",
        "'alerts_connected':",
        "'alerts_fallback':",
        "'alert_source_label':",
    ):
        assert field in rows
    assert '_snapshot_payload(system)' in rows
    assert '_alert_view(payload)' in rows
    assert "alerts_connected = analytics_usable and bool(alert_stream.get('connected'))" in rows
    assert 'load_alert_stream(' not in rows
    assert 'get_alertmanager_alerts(' not in rows
    for field in ('row.inventory_ready', 'row.snapshot_ready', 'row.alerts_connected', 'row.alerts_fallback'):
        assert field in health
    assert 'bg-status-warning' in health
    assert 'bg-status-normal' in health
    assert 'bg-status-unknown' in health
    assert 'row.alert_source_label' in health
    assert 'sr-only' in health
    assert 'row.alerts_status' in kubernetes
    assert 'row.inventory_ready' in registry
    assert 'row.metrics_ready' in registry
    assert 'row.security_ready' in registry
    assert 'for item in dashboard.freshness' in freshness
    for route in (storage_routes, registry_routes, kubernetes_routes):
        assert 'normalize_operational_tab' in route
        assert 'normalize_dashboard_page_size' in route
    for tab in ("'overview'", "'capacity'", "'signals'", "'reporting'"):
        assert tab in application
