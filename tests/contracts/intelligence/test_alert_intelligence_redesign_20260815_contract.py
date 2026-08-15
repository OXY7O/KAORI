from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_keeps_global_summary_and_tabbed_section_workspace() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')

    assert '_alert_intelligence_summary.html' in page
    assert '_alert_intelligence_workspace.html' in page
    assert "payload.tab == 'correlation'" in page
    assert "payload.tab == 'delivery'" in page
    assert "payload.tab == 'evidence'" in page
    assert '_alert_intelligence_alerts.html' in page
    assert 'Alert Intelligence Summary' in summary
    assert 'Matching Alerts' in summary
    assert 'Critical' in summary
    assert 'Warning' in summary
    assert 'Recommendations' in summary
    assert "intelligence_ui.link_tabs(workspace_tabs, payload.tab, 'Alert Intelligence Sections')" in workspace


def test_alert_intelligence_tabs_are_section_owned_and_informative() -> None:
    service = read('app/alert_intelligence/service.py')
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


def test_alert_intelligence_filters_auto_refresh_without_apply() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert 'hx-trigger="input changed delay:350ms' in workspace
    assert 'change from:select' in workspace
    assert 'Reset Filters' in workspace
    assert '>Apply<' not in workspace
    assert 'Alert Record Filters' in workspace
    assert 'Operational Scope' in workspace


def test_alert_intelligence_filter_geometry_keeps_compact_scope_and_record_rows() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert 'lg:grid-cols-12' in workspace
    for token in ('lg:col-span-3', 'lg:col-span-5', 'lg:col-span-4', 'lg:col-span-6'):
        assert token in workspace
    assert "payload.tab == 'alerts'" in workspace
    assert 'Search' in workspace
    assert 'Severity' in workspace
    assert 'State' in workspace


def test_alert_intelligence_keeps_provider_lifecycle_and_correlation_boundaries_explicit() -> None:
    alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')
    evidence = read('app/templates/intelligence/partials/_alert_intelligence_evidence.html')

    assert 'Alertmanager is preferred in Automatic mode' in alerts
    assert 'Prometheus ALERTS remains the fallback evidence path' in alerts
    assert 'contextual correlation, not a claim that every finding was caused by every alert' in correlation
    assert 'External Alert Authority' in evidence
    assert 'KAORI Owns' in evidence


def test_alert_intelligence_htmx_refreshes_full_page_context_for_scope_changes() -> None:
    routes = read('app/alert_intelligence/routes.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert "render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)" in routes
    assert 'hx-target="#alert-intelligence-page-content"' in workspace
    assert 'hx-swap="outerHTML show:none focus-scroll:false"' in workspace
    assert 'hx-sync="#alert-intelligence-page-content:replace"' in workspace
    assert 'name="tab" value="{{ payload.tab }}"' in workspace
