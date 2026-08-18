from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_keeps_global_summary_and_single_tabbed_workspace_surface() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')

    assert '_alert_intelligence_summary.html' in page
    assert '_alert_intelligence_workspace.html' in page
    assert "payload.tab == 'correlation'" not in page
    assert "payload.tab == 'delivery'" not in page
    assert "payload.tab == 'evidence'" not in page
    assert '_alert_intelligence_alerts.html' not in page
    assert 'Alert Intelligence Summary' in summary
    assert 'Matching Alerts' in summary
    assert 'Critical' in summary
    assert 'Warning' in summary
    assert 'Recommendations' in summary
    assert 'components/content_tabs.html' in workspace
    assert 'content_tabs.render_links(' in workspace
    assert "data_namespace='alert-intelligence'" in workspace
    assert 'nowrap=true' in workspace
    assert "hx_sync='#alert-intelligence-page-content:replace'" in workspace
    assert 'data-alert-intelligence-active-section' in workspace
    for partial in (
        '_alert_intelligence_alerts.html',
        '_alert_intelligence_correlation.html',
        '_alert_intelligence_delivery.html',
        '_alert_intelligence_evidence.html',
    ):
        assert partial in workspace
    assert 'intelligence_ui.link_tabs(' not in workspace


def test_alert_intelligence_workspace_places_tabs_before_compact_operational_context() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert workspace.index('content_tabs.render_links(') < workspace.index('Operational Context')
    assert 'Operational Scope' not in workspace
    assert 'id="alert-intelligence-context-form"' in workspace
    assert 'hx-trigger="change from:select"' in workspace
    assert (
        'Selected asset and alert source define the evidence context shared across every Alert Intelligence section.'
        in workspace
    )
    assert 'bg-surface-hover px-4 py-4 sm:px-5' not in workspace


def test_alert_intelligence_tabs_are_section_owned_and_informative() -> None:
    service = read('app/intelligence/alert_intelligence/service.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')
    delivery = read('app/templates/intelligence/partials/_alert_intelligence_delivery.html')
    evidence = read('app/templates/intelligence/partials/_alert_intelligence_evidence.html')

    assert "_VALID_TABS = {'alerts', 'correlation', 'delivery', 'evidence'}" in service
    assert "tab = _choice(args.get('tab'), _VALID_TABS, 'alerts')" in service
    for label in ('Alert Records', 'Correlation & Guidance', 'Notification Delivery', 'Evidence & Ownership'):
        assert label in workspace

    for required in ('Alert Source Context', 'Resolved Source', 'Runtime', 'Lifecycle Authority'):
        assert required in alerts
    for required in ('Active Recommendations', 'Catalog Rules', 'Relationship', 'Contextual Only'):
        assert required in correlation
    for required in ('Delivery Status', 'Operational Channels', 'Recent Deliveries'):
        assert required in delivery
    for required in ('Detection', 'Lifecycle', 'Interpretation', 'Execution'):
        assert required in evidence

    for partial in (alerts, correlation, delivery, evidence):
        assert 'intelligence_ui.section(' not in partial
        assert 'data-alert-intelligence-panel=' in partial


def test_alert_record_filters_are_tab_local_auto_refresh_and_keep_reset() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')

    assert 'Alert Record Filters' not in workspace
    assert 'Reset Filters' not in workspace
    assert 'id="alert-intelligence-filter-form"' in alerts
    assert 'hx-trigger="input changed delay:350ms' in alerts
    assert 'change from:select' in alerts
    assert 'clear_filters_action' in alerts
    assert '>Apply<' not in alerts
    assert 'source=payload.source' in alerts


def test_alert_intelligence_context_and_record_filter_geometry_are_distinct() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')

    assert 'table_ui.filter_layout_classes()' in workspace
    assert 'lg:grid-cols-12' not in workspace
    assert 'lg:col-span-' not in workspace
    assert 'table_ui.filter_layout_classes()' in alerts
    assert 'lg:grid-cols-12' not in alerts
    assert 'lg:col-span-' not in alerts
    assert 'Search' in alerts
    assert 'Severity' in alerts
    assert 'State' in alerts


def test_alert_intelligence_keeps_provider_lifecycle_and_correlation_boundaries_explicit() -> None:
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')
    evidence = read('app/templates/intelligence/partials/_alert_intelligence_evidence.html')

    assert 'Alertmanager is preferred in Automatic mode' in alerts
    assert 'Metrics Source ALERTS remains the fallback evidence path' in alerts
    assert 'contextual correlation, not a claim that every finding was caused by every alert' in correlation
    assert 'External Alert Authority' in evidence
    assert 'KAORI Owns' in evidence


def test_alert_intelligence_htmx_refreshes_full_page_context_for_scope_changes() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')

    assert "render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)" in routes
    assert 'hx-target="#alert-intelligence-page-content"' in workspace
    assert 'hx-swap="outerHTML show:none focus-scroll:false"' in workspace
    assert 'hx-sync="#alert-intelligence-page-content:replace"' in workspace
    assert 'name="tab" value="{{ payload.tab }}"' in workspace
    assert 'name="domain" value="{{ payload.domain }}"' in alerts
    assert 'name="asset" value="{{ payload.selected_asset_key }}"' in alerts
    assert 'name="source" value="{{ payload.source }}"' in alerts
