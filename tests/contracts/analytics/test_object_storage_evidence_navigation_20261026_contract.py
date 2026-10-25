"""Central Object Storage Analytics Evidence navigation and retained domain context contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = "app/templates/storage/object_storage/analytics/partials"


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_only_overview_owns_data_and_evidence_tab() -> None:
    overview = read(f"{PARTIALS}/_overview_workspace.html")
    assert "('evidence', 'Data & Evidence', 'list-checks')" in overview
    assert 'data-analytics-tab-panel="evidence"' in overview
    assert 'partials/_metrics_readiness.html' in overview
    assert 'partials/_overview_evidence_context.html' in overview

    for filename in (
        '_capacity_workspace.html',
        '_performance_workspace.html',
        '_top_consumers_workspace.html',
        '_forecast_workspace.html',
        '_alerts_workspace.html',
    ):
        workspace = read(f"{PARTIALS}/{filename}")
        assert "('evidence', 'Evidence', 'list-checks')" not in workspace
        assert 'data-analytics-tab-panel="evidence"' not in workspace
        assert 'panel-evidence' not in workspace
        assert 'partials/_domain_evidence_context.html' in workspace


def test_domain_context_preserves_source_authority_and_deep_link() -> None:
    component = read(f"{PARTIALS}/_domain_evidence_context.html")
    controller = read('app/static/js/analytics/controls.js')
    routes = read('app/storage/object_storage/analytics/routes.py')

    assert "url_for('analytics.object_storage_overview'" in component
    for query in ('system_id=system.id', 'time_range=selected_time_range', "tab='evidence'"):
        assert query in component
    assert 'data-object-storage-central-evidence-link' in component
    assert 'data-object-storage-domain-evidence-context' in component
    assert "searchParams.get('tab')" in controller
    assert 'if (allowedTabs.includes(requestedTab)) return requestedTab' in controller
    assert "return _render('overview')" in routes

    for source in (
        'analytics_materialization.label',
        'analytics_materialization.tone',
        'forecast_materialization.label',
        'forecast_materialization.tone',
        'alert_source.label',
        'alert_source.tone',
        'alert_source.resolved_label',
        'metrics_source.provider_label',
    ):
        assert source in component
    assert "default('Unknown')" in component
    assert 'No live provider' not in component or 'no live provider' in component.lower()


def test_owned_reconciliation_forecast_and_alert_detail_are_not_lost() -> None:
    capacity = read(f"{PARTIALS}/_capacity_workspace.html")
    forecast = read(f"{PARTIALS}/_forecast_workspace.html")
    alerts = read(f"{PARTIALS}/_alerts_workspace.html")
    consumers = read(f"{PARTIALS}/_top_consumers_workspace.html")
    performance = read(f"{PARTIALS}/_performance_workspace.html")
    for marker in (
        'data-object-storage-capacity-reconciliation',
        'partials/_reconciliation.html',
        '<details',
    ):
        assert marker in capacity
    for marker in (
        "('worker', 'Worker & Method', 'cpu')",
        'partials/_forecast_worker_status.html',
        'partials/_forecast_methodology.html',
    ):
        assert marker in forecast
    for marker in (
        'data-object-storage-alert-source-details',
        'partials/_alerts_source_evidence.html',
        "('signals', 'Anomaly Signals', 'list-tree')",
    ):
        assert marker in alerts
    assert 'partials/_bucket_table.html' in consumers
    assert 'partials/_performance_analysis.html' in performance


def test_changed_evidence_templates_compile_without_unknown_flask_filters() -> None:
    jinja = Environment()
    jinja.filters['user_datetime'] = lambda value, fallback=None: value or fallback
    for filename in (
        '_overview_workspace.html',
        '_capacity_workspace.html',
        '_performance_workspace.html',
        '_top_consumers_workspace.html',
        '_forecast_workspace.html',
        '_alerts_workspace.html',
        '_domain_evidence_context.html',
    ):
        jinja.from_string(read(f"{PARTIALS}/{filename}"))
