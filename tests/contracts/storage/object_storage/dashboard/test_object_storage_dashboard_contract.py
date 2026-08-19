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
    assert "'capacity': 'storage/object_storage/dashboard/partials/_capacity.html'" in routes
    assert "'signals': 'storage/object_storage/dashboard/partials/_signals.html'" in routes
    assert "'reporting': 'storage/object_storage/dashboard/partials/_reporting.html'" in routes

    assert 'read_analytics_snapshot(' in service
    assert 'get_forecast_snapshot(' in service
    assert 'analytics_snapshot_state(' in service
    assert 'forecast_snapshot_state(' in service
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
    kubernetes_content = read('app/templates/kubernetes/dashboard/partials/_content.html')

    for label in ('Operations Overview', 'Capacity & Demand', 'Signals & Actions', 'Reporting'):
        assert label in content
        assert label in kubernetes_content
    assert "components/workspace_tabs.html" in content
    assert "components/operational_section_card.html" in content
    assert "hx-get=\"{{ url_for('object_storage_dashboard.section', section=tab_key) }}?{{ dashboard_query }}\"" in content
    assert 'hx-trigger="revealed"' in content
    assert "hx-get=\"{{ url_for('object_storage_dashboard.section', section='kpi_cards') }}?{{ dashboard_query }}\"" in content
    assert 'hx-trigger="load"' in content
    assert 'All Systems' in content
    assert 'No live provider query on page load' in content


def test_dashboard_sections_are_object_storage_specific_and_committed_evidence_owned() -> None:
    overview = read('app/templates/storage/object_storage/dashboard/partials/_overview.html')
    capacity = read('app/templates/storage/object_storage/dashboard/partials/_capacity.html')
    signals = read('app/templates/storage/object_storage/dashboard/partials/_signals.html')
    reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting.html')

    for token in ('System Health Summary', 'Inventory Snapshot', 'Data Freshness'):
        assert token in overview
    for token in ('Capacity Snapshot', 'Forecast & Growth Risk', 'Top Bucket Consumers'):
        assert token in capacity
    for token in ('Alerts Summary', 'Operational Response', 'committed dashboard evidence'):
        assert token in signals
    for token in ('Reporting Summary', 'Evidence Readiness', 'Object Storage report'):
        assert token in reporting

    assert 'overflow-x-auto' not in overview
    assert 'overflow-x-auto' not in capacity
    assert 'overflow-x-auto' not in signals


def test_object_storage_analytics_verifier_tracks_current_snapshot_contract() -> None:
    verifier = read('scripts/verify_object_storage_analytics.py')

    assert "assert 'Operational Metrics Contract' in readiness" in verifier
    assert "assert 'Readiness By Evidence Domain' in readiness" in verifier
    assert "assert 'Object Storage → Metrics → Analytics Snapshot' in dependency_blocker" in verifier
    assert "assert 'readiness_step_count = 3' in hero_blocked" in verifier
    assert "for label in ('Forecast Outlook', 'Usage Trend', 'Bucket Forecasts', 'Worker & Method', 'Evidence')" in verifier
