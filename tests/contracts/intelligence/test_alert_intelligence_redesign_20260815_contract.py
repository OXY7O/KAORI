from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_alert_intelligence_uses_standalone_summary_and_sequential_workspaces() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')

    assert "_alert_intelligence_summary.html" in page
    assert "_alert_intelligence_workspace.html" in page
    assert "_alert_intelligence_correlation.html" in page
    assert "_alert_intelligence_delivery.html" in page
    assert "_alert_intelligence_evidence.html" in page
    assert 'Alert Intelligence Summary' in summary
    assert 'Matching Alerts' in summary
    assert 'Critical' in summary
    assert 'Warning' in summary
    assert 'Recommendations' in summary


def test_alert_intelligence_filters_auto_refresh_without_apply_or_tabs() -> None:
    service = read('app/alert_intelligence/service.py')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')

    assert 'hx-trigger="input changed delay:350ms' in workspace
    assert 'change from:select' in workspace
    assert 'Reset Filters' in workspace
    assert '>Apply<' not in workspace
    assert 'link_tabs(' not in workspace
    assert 'link_tabs(' not in page
    assert '_VALID_TABS' not in service
    assert "'tab':" not in service


def test_alert_intelligence_filter_geometry_is_two_row_desktop_standard() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')

    assert 'lg:grid-cols-12' in workspace
    for token in ('lg:col-span-3', 'lg:col-span-5', 'lg:col-span-4', 'lg:col-span-6'):
        assert token in workspace
    assert 'Alert Filters' in workspace
    assert 'Results refresh automatically' in workspace


def test_alert_intelligence_keeps_provider_lifecycle_and_correlation_boundaries_explicit() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')
    evidence = read('app/templates/intelligence/partials/_alert_intelligence_evidence.html')

    assert 'Alertmanager' in workspace
    assert 'Prometheus ALERTS' in workspace
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
