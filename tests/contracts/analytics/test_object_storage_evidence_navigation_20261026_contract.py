"""Central Object Storage Analytics Evidence navigation and retained domain context contracts."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = 'app/templates/storage/object_storage/analytics/partials'


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_only_overview_owns_data_and_evidence_tab() -> None:
    overview = read(f'{PARTIALS}/_overview_workspace.html')
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
        workspace = read(f'{PARTIALS}/{filename}')
        assert "('evidence', 'Evidence', 'list-checks')" not in workspace
        assert 'data-analytics-tab-panel="evidence"' not in workspace
        assert 'panel-evidence' not in workspace
        assert 'partials/_domain_evidence_context.html' in workspace


def test_domain_context_preserves_source_authority_and_deep_link() -> None:
    component = read(f'{PARTIALS}/_domain_evidence_context.html')
    controller = read('app/static/js/analytics/controls.js')
    routes = read('app/storage/object_storage/analytics/routes.py')

    assert "url_for('analytics.object_storage_overview'" in component
    for query in (
        'system_id=system.id',
        'time_range=selected_time_range',
        "tab='evidence'",
    ):
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
    assert "context_status = analytics_materialization.label|default('Unavailable')" in component
    assert "context_status = forecast_materialization.label|default('Unavailable')" in component


def test_owned_reconciliation_forecast_and_alert_detail_are_not_lost() -> None:
    capacity = read(f'{PARTIALS}/_capacity_workspace.html')
    forecast = read(f'{PARTIALS}/_forecast_workspace.html')
    alerts = read(f'{PARTIALS}/_alerts_workspace.html')
    consumers = read(f'{PARTIALS}/_top_consumers_workspace.html')
    performance = read(f'{PARTIALS}/_performance_workspace.html')
    for marker in (
        'data-object-storage-capacity-reconciliation-dialog',
        'data-kaori-native-dialog',
        'partials/_reconciliation.html',
    ):
        assert marker in capacity
    assert '<details' not in capacity
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


def test_capacity_summary_uses_shared_guide_and_native_reconciliation_dialog() -> None:
    analysis = read(f'{PARTIALS}/_capacity_analysis.html')
    capacity = read(f'{PARTIALS}/_capacity_workspace.html')
    context = read(f'{PARTIALS}/_domain_evidence_context.html')
    controller = read('app/static/js/native_dialogs.js')
    reconciliation = read(f'{PARTIALS}/_reconciliation.html')

    assert 'components/info_tip.html' in analysis
    assert 'object-storage-capacity-operating-boundary-guide' in analysis
    assert "variant='guide'" in analysis
    assert 'Capacity Operating Boundary' in analysis
    assert 'metrics.capacity_posture.status' in analysis
    assert 'metrics.capacity_usage.trend_direction_label' in analysis
    assert 'Growth describes observed usage direction inside' not in analysis
    assert 'if not metrics.capacity_usage.trend_evidence_available' in analysis
    assert 'At least two valid historical samples are required' in analysis

    dialog_id = 'object-storage-capacity-reconciliation-dialog'
    assert "page_key == 'capacity'" in context
    assert 'data-object-storage-reconciliation-modal-trigger' in context
    assert 'data-kaori-dialog-open' in context
    assert f'data-dialog-target="{dialog_id}"' in context
    assert f'aria-controls="{dialog_id}"' in context
    assert 'View Reconciliation' in context
    assert context.count('class="{{ evidence_action_classes }}"') == 2
    assert 'data-object-storage-central-evidence-link' in context

    assert f'<dialog id="{dialog_id}"' in capacity
    assert 'data-kaori-native-dialog' in capacity
    assert 'aria-labelledby="object-storage-capacity-reconciliation-title"' in capacity
    assert 'aria-describedby="object-storage-capacity-reconciliation-description"' in capacity
    assert capacity.count('data-kaori-dialog-close') == 2
    assert 'role="document"' in capacity
    assert 'max-h-[calc(100dvh-2rem)]' in capacity
    assert 'overflow-y-auto' in capacity
    assert 'reconciliation_embedded = true' in capacity
    assert 'metrics.reconciliation' in reconciliation
    assert 'item.delta_display' in reconciliation
    assert 'item.delta_percent_display' in reconciliation
    assert 'item.tone' in reconciliation
    assert 'data-kaori-dialog-open' in controller
    assert "dialog.showModal()" in controller
    assert "dialog.close()" in controller


def test_evidence_coverage_and_reconciliation_use_shared_tables() -> None:
    context = read(f'{PARTIALS}/_overview_evidence_context.html')
    reconciliation = read(f'{PARTIALS}/_reconciliation.html')
    capacity = read(f'{PARTIALS}/_capacity_workspace.html')

    assert 'data-object-storage-coverage-table' in context
    assert 'data-object-storage-evidence-domain="{{ domain|lower }}"' in context
    assert 'table_ui.table_classes(' in context
    assert 'table_label.status_label(state, tone' in context
    assert 'whitespace-nowrap' in context
    assert 'data-object-storage-reconciliation-table' in reconciliation
    assert 'table_ui.table_classes(' in reconciliation
    for original in (
        'item.operational_display',
        'item.inventory_display',
        'item.delta_display',
        'item.delta_percent_display',
        'item.status',
        'item.tone',
    ):
        assert original in reconciliation
    assert 'reconciliation_embedded = true' in context
    assert 'reconciliation_embedded = true' in capacity
    assert 'data-object-storage-reconciliation-context' in reconciliation
    assert 'Observation times differ; drift is a review signal.' in reconciliation


def test_evidence_authority_explanations_are_single_line_at_desktop_width() -> None:
    context = read(f'{PARTIALS}/_overview_evidence_context.html')
    assert 'Identity, quota, protection, and usage fallback.' in context
    assert 'Committed alert lifecycle and routing evidence.' in context
    assert 'Worker projection; no Inventory fallback.' in context
    assert 'Alertmanager first; ALERTS fallback is rule-state only.' in context
    assert 'truncate whitespace-nowrap' in context
    assert 'block whitespace-nowrap' in context


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
        '_overview_evidence_context.html',
        '_reconciliation.html',
    ):
        jinja.from_string(read(f'{PARTIALS}/{filename}'))
