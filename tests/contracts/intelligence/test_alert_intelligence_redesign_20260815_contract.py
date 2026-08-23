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
    assert (
        'Manage alert routing, silences, recovery verification, and incident history from committed evidence.' in page
    )
    assert page.count('page_hero.meta_label(') == 3
    assert '_alert_intelligence_summary.html' in page
    assert '_alert_intelligence_workspace.html' in page
    assert "'resolved'" in service
    assert "if tab == 'history':" in service
    for label in ('Overview', 'Active Alerts', 'Routing & Channels', 'Templates', 'Silences', 'Resolved'):
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
    assert 'id="alert-intelligence-domain-select"' in workspace
    assert 'id="alert-intelligence-asset-select"' in workspace
    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]
    assert 'hx-get="{{ url_for(\'alert_intelligence.index\') }}"' in context_form
    assert 'hx-trigger="change"' in context_form
    assert 'name="domain"' in context_form
    assert 'name="asset"' in context_form
    assert 'hx-disabled-elt=' not in context_form
    assert 'hx-include=' not in context_form
    assert 'id="alert-operations-filter-form"' in active
    assert 'id="alert-operations-active-registry"' in active
    assert 'alert-operations-active-loading' in active
    assert 'loading_bar.render' in active
    assert 'Active Alert Triage' in active
    assert 'Triage Guidance' in active
    assert 'bg-kaori-soft' in active
    assert 'Quick Views' in active
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

    for required in ('Alert Operations Snapshot', 'Lifecycle Control', 'Operational Readiness', 'Ownership Boundary'):
        assert required in overview
    assert 'Review' in active
    for required in (
        'Acknowledge',
        'Update Owner',
        'Mark Mitigating',
        'Silence Delivery',
        'Resolution Summary',
        'Verification Evidence',
    ):
        assert required in case_workspace
    for required in ('Routing Policies', 'Policy Registry', 'Channel Readiness', 'Create Routing Policy', 'Notification Channels'):
        assert required in routing
    assert "table_ui.table_classes('min-w-[1180px]')" in routing
    assert 'Policy Details' in routing
    assert '<details class="group border-t border-outline-subtle">' in routing
    assert 'Routing Eligibility' in routing
    assert 'Policy Checklist' in routing
    assert 'table_registry.footer' in routing
    assert 'payload.selected_policy' in routing
    assert 'Integrations → Notification Channels' in routing
    assert 'Template Registry' in templates
    assert '<details class="group bg-surface-card">' in templates
    assert 'Save Override' in templates
    assert 'Active Delivery Silences' in silences
    assert 'table_registry.footer' in silences
    for required in ('Resolved Alerts', 'Resolution Evidence', 'Postmortem', 'Verification Pending'):
        assert required in history
    assert 'table_registry.filter_form' in history
    assert 'table_registry.footer' in history


def test_alert_operations_registry_tables_use_canonical_five_row_pagination() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "page=args.get('routing_page', 1)" in service
    assert "per_page=args.get('routing_per_page', 5)" in service
    assert "page=args.get('silence_page', 1)" in service
    assert "per_page=args.get('silence_per_page', 5)" in service
    assert "per_page=args.get('history_per_page', 5)" in service
    assert "'routing_pagination': routing_pagination" in service
    assert "'silence_pagination': silence_pagination" in service


def test_alert_intelligence_web_paths_stay_database_and_snapshot_only() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    worker = read('app/platform_operations/notifications/alert_delivery/tasks.py')

    for forbidden in ('load_alerts_by_source', 'load_alert_stream'):
        assert forbidden not in service
        assert forbidden not in routes
    assert "AlertCase.source_type == 'recommendation'" in service
    assert 'reconcile_alert_cases' not in worker
    assert 'reconcile_recommendation_alert_cases' in worker
    assert 'dispatch_case_notifications' in worker
