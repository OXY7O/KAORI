from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_is_alert_operations_workspace() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'Alert Operations' in page
    assert '_alert_intelligence_summary.html' in page
    assert '_alert_intelligence_workspace.html' in page
    assert "_VALID_TABS = {'overview', 'active', 'routing', 'templates', 'silences', 'history'}" in service
    for label in ('Overview', 'Active Alerts', 'Routing & Channels', 'Templates', 'Silences', 'History'):
        assert label in workspace
    for label in ('Active Alerts', 'Acknowledged', 'Silenced', 'Resolved Today'):
        assert label in summary
    assert 'components/content_tabs.html' in workspace
    assert "data_namespace='alert-operations'" in workspace
    assert "hx_sync='#alert-intelligence-page-content:replace'" in workspace


def test_active_alert_filters_are_tab_local_auto_refresh_and_keep_clear_filters() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')

    assert 'Operational Context' in workspace
    assert 'id="alert-intelligence-context-form"' in workspace
    assert 'id="alert-operations-filter-form"' in active
    assert 'hx-trigger="input changed delay:350ms from:input, change from:select"' in active
    assert 'Search' in active
    assert 'Severity' in active
    assert 'Workflow' in active
    assert 'Clear Filters' in active
    assert 'Reset Filters' not in active
    assert '>Apply<' not in active


def test_alert_operations_sections_own_distinct_operator_responsibilities() -> None:
    overview = read('app/templates/intelligence/partials/_alert_ops_overview.html')
    active = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    case_workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    templates = read('app/templates/intelligence/partials/_alert_ops_templates.html')
    silences = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    history = read('app/templates/intelligence/partials/_alert_ops_history.html')

    assert 'Lifecycle Posture' in overview
    assert 'Review' in active
    for required in ('Acknowledge', 'Update Owner', 'Mark Mitigating', 'Silence Delivery', 'Resolution Summary', 'Verification Evidence'):
        assert required in case_workspace
    assert 'Notification Channels' in routing
    assert 'Integrations → Notification Channels' in routing
    assert 'template.event_label' in templates
    assert 'KAORI Delivery Silence' in silences
    for required in ('Resolved & Historical Alerts', 'Resolution Evidence', 'Postmortem'):
        assert required in history


def test_alert_intelligence_web_paths_stay_database_and_snapshot_only() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')

    for forbidden in ('load_alerts_by_source', 'load_alert_stream'):
        assert forbidden not in service
        assert forbidden not in routes
    assert 'load_snapshot_rows' in service
    assert 'reconcile_alert_cases' in worker
    assert 'dispatch_case_notifications' in worker
