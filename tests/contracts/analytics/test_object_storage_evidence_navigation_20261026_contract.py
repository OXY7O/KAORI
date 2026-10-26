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


def test_forecast_guides_compact_trend_and_detached_records_reuse_kaori_contracts() -> None:
    outlook = read(f'{PARTIALS}/_forecast_analysis.html')
    workspace = read(f'{PARTIALS}/_forecast_workspace.html')
    trend = read(f'{PARTIALS}/_trend.html')
    buckets = read(f'{PARTIALS}/_bucket_forecasts.html')
    records = read(f'{PARTIALS}/_bucket_forecast_table.html')
    worker = read(f'{PARTIALS}/_forecast_worker_status.html')

    for source, guide in (
        (outlook, 'object-storage-forecast-operating-boundary-guide'),
        (trend, 'object-storage-storage-usage-forecast-'),
        (buckets, 'object-storage-bucket-forecast-watch-guide'),
        (worker, 'object-storage-forecast-worker-refresh-guide'),
    ):
        assert 'components/info_tip.html' in source
        assert 'info_tip.render(' in source
        assert guide in source
        assert "variant='guide'" in source

    assert 'object_storage_trend_instance = "outlook"' in outlook
    assert 'object_storage_trend_instance = "trend"' in workspace
    assert "object_storage_trend_instance|default('trend')" in trend
    assert 'Operational Reading' not in outlook
    assert 'interpretation_callout(' not in outlook
    for field in (
        'metrics.forecast_display.growth_per_day',
        'metrics.forecast_display.projected_7d',
        'metrics.forecast_display.projected_30d',
        'metrics.forecast_display.days_to_capacity',
    ):
        assert field in outlook

    assert "compact_forecast_workspace = page_key == 'forecast' and trend_mode == 'forecast'" in trend
    assert 'compact_overview_trend = compact_usage_overview or compact_forecast_overview or compact_forecast_workspace' in trend
    assert 'grid gap-px bg-outline-subtle sm:grid-cols-3' in trend
    assert 'data-object-storage-overview-trend-summary' in trend
    assert 'data-object-storage-projection-points' in trend
    assert 'data-object-storage-forecast-interpretation' in trend
    assert 'data-object-storage-chart-container' in trend
    assert 'Historical Growth / Day' in trend
    assert "data-object-storage-capacity-trend-facts" in trend
    assert "compact_usage_overview = page_key == 'overview' and trend_mode == 'usage'" in trend

    separate_table = (
        '</section>\n{% if bucket_forecasts %}\n'
        '    {% include "storage/object_storage/analytics/partials/_bucket_forecast_table.html" %}'
    )
    assert separate_table in buckets
    assert 'data-object-storage-bucket-forecast-chart-panel' in buckets
    assert "bucket_forecast_summary.ready_count|default(0)" in buckets
    assert 'analysis_surface.evidence_shell_classes()' in records
    assert 'data-kaori-object-storage-bucket-forecast-table' in records
    assert 'table_ui.block_icon_classes()' in records
    assert 'xl:whitespace-nowrap' in records
    assert 'Review forecast-ready and evidence-gap buckets; filters retain the selected system and history window.' in records
    assert 'object-storage-bucket-forecast-table-loading-indicator' in records
    assert 'forecast_bucket_per_page' in records
    assert 'registry_ui.clear_filters_action' in records
    assert 'analytics.object_storage_bucket_forecast_table' in records
    assert 'forecast_history_state' in records
    assert 'forecast_watch' in records
    assert 'data-object-storage-forecast' not in worker
    assert 'forecast_materialization.generated_at' in worker


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
    assert 'dialog.showModal()' in controller
    assert 'dialog.close()' in controller


def test_capacity_trend_and_quota_guides_reuse_shared_component_roles() -> None:
    trend = read(f'{PARTIALS}/_trend.html')
    pressure = read(f'{PARTIALS}/_capacity_pressure.html')
    table = read(f'{PARTIALS}/_bucket_table.html')
    service = read('app/storage/object_storage/analytics/bucket_table.py')

    assert 'object-storage-capacity-usage-trend-guide' in trend
    assert "page_key == 'capacity' and trend_mode == 'usage'" in trend
    assert 'data-object-storage-capacity-trend-facts' in trend
    assert "analysis_surface.role_icon_classes('status', trend_summary.tone" in trend
    assert "analysis_surface.role_icon_classes('insight', 'info', 'compact')" in trend
    assert 'trend_summary.sample_count' in trend
    assert 'trend_summary.delta_percent_display' in trend
    assert 'object-storage-capacity-quota-pressure-guide' in pressure
    assert "variant='guide'" in pressure
    assert 'metrics.capacity_usage.quota_tone' in pressure
    assert 'Inventory fills only supported missing bucket metrics.' in table
    assert 'xl:whitespace-nowrap' in table
    assert 'table_ui.filter_layout_classes()' in table
    assert 'table_ui.filter_select_classes()' in table
    assert 'bucket_quota_state' in table
    assert 'bucket_quota_pressure' in table
    assert 'clear_filters_action' in table
    assert 'default=5' in service
    assert "query_params['bucket_quota_state']" in service
    assert "query_params['bucket_quota_pressure']" in service


def test_capacity_bucket_header_uses_shared_icon_and_right_aligned_clear_filters() -> None:
    table = read(f'{PARTIALS}/_bucket_table.html')
    header = table.split('</header>', 1)[0]
    filter_form = table.split('<form id="object-storage-bucket-table-filter"', 1)[1].split('</form>', 1)[0]

    assert "page_key == 'capacity'" in header
    assert 'table_ui.block_icon_classes()' in header
    assert "page_key in ['capacity', 'performance']" in header
    assert "data-lucide=\"{{ 'boxes' if page_key == 'capacity' else 'database-zap' }}\"" in header
    assert 'Bucket Capacity Records' in header
    assert 'table_label.result_count(' in header
    assert 'registry_ui.clear_filters_action(' in header
    assert 'items-center justify-end' in header
    assert 'lead=false' in header
    assert 'registry_ui.clear_filters_action(' not in filter_form
    assert 'bucket_q' in filter_form
    assert 'bucket_quota_state' in filter_form
    assert 'bucket_quota_pressure' in filter_form
    assert 'bucket_per_page' in filter_form


def test_capacity_workspace_recommendations_and_controls_use_title_level_kaori_guides() -> None:
    capacity = read(f'{PARTIALS}/_capacity_workspace.html')
    recommendations = read(f'{PARTIALS}/_recommendations_workspace.html')
    controls = read(f'{PARTIALS}/_controls.html')
    shared = read('app/templates/analytics/components/_controls_readiness.html')
    overview = read(f'{PARTIALS}/_overview_workspace.html')

    assert 'components/info_tip.html' in capacity
    assert 'object-storage-capacity-workspace-guide' in capacity
    assert 'Capacity &amp; Usage Workspace' in capacity
    assert "placement='right', variant='guide'" in capacity
    assert 'data-analytics-tabset-id="object-storage-capacity-content"' in capacity
    assert 'partials/_domain_evidence_context.html' in capacity

    assert 'components/info_tip.html' in recommendations
    assert "'object-storage-' ~ page_key ~ '-recommendations-guide'" in recommendations
    assert "{% if page_key == 'capacity' %}" not in recommendations
    assert '{{ recommendation_context_label }} Recommendations' in recommendations
    assert "placement='right', variant='guide'" in recommendations
    assert 'url_for(request.endpoint' in recommendations

    assert "'object-storage-analytics-controls-readiness-' ~ page_key ~ '-guide'" in controls
    assert "if page_key == 'capacity' else ''" not in controls
    assert 'title_accessory=analytics_controls_guide' in controls
    assert 'data-analytics-controls-readiness' in shared
    assert "title_accessory=''" in shared
    assert '{% if title_accessory %}' in shared
    assert '{{ title_accessory }}' in shared
    assert '<h2 class="mt-1 {{ table_ui.block_title_classes() }}">{{ title }}</h2>' in shared
    assert 'hx-target="#object-storage-analytics-page"' in controls
    assert 'object-storage-capacity-workspace-guide' not in overview


def test_performance_guides_copy_and_bucket_source_filter_follow_kaori_standard() -> None:
    workspace = read(f'{PARTIALS}/_performance_workspace.html')
    reliability = read(f'{PARTIALS}/_performance_analysis.html')
    traffic = read(f'{PARTIALS}/_performance_traffic.html')
    buckets = read(f'{PARTIALS}/_bucket_table.html')
    recommendations = read(f'{PARTIALS}/_recommendations_workspace.html')
    controls = read(f'{PARTIALS}/_controls.html')
    service = read('app/storage/object_storage/analytics/bucket_table.py')
    overview = read(f'{PARTIALS}/_overview_workspace.html')

    for source, guide_id in (
        (workspace, 'object-storage-performance-workspace-guide'),
        (reliability, 'object-storage-request-path-boundary-guide'),
        (traffic, 'object-storage-throughput-request-direction-guide'),
        (buckets, 'object-storage-bucket-request-path-records-guide'),
    ):
        assert guide_id in source
        assert 'components/info_tip.html' in source
        assert "variant='guide'" in source

    assert 'Error ratio reflects reliability, not response latency or client experience.' in reliability
    assert 'Inflight reflects work; waiting requests and offline nodes indicate pressure.' in reliability
    assert 'metrics.error_ratio is not none' in reliability
    assert 'Review boundary ≥ 5%' in reliability
    assert 'Critical boundary ≥ 10%' in reliability
    assert "metrics.performance.top_request_bucket_value ~ ' peak request rate · Coverage: '" in traffic
    assert "metrics.performance.top_error_bucket_value ~ ' peak error ratio · Coverage: '" in traffic
    assert 'metrics.performance.bucket_request_coverage_display' in traffic
    assert 'metrics.performance.bucket_error_coverage_display' in traffic

    assert "page_key in ['capacity', 'performance']" in buckets
    assert "data-lucide=\"{{ 'boxes' if page_key == 'capacity' else 'database-zap' }}\"" in buckets
    assert 'Request metrics never fall back to Inventory' not in buckets
    assert 'Request Rate and Error Rate are metrics-only' in buckets
    assert "page_key == 'performance'" in buckets
    assert 'name="bucket_usage_context"' in buckets
    assert 'table_ui.filter_select_classes()' in buckets
    assert 'registry_ui.clear_filters_action(' in buckets
    assert 'lead=false' in buckets
    assert "bucket_table.usage_context != 'all'" in buckets
    assert 'bucket_usage_context' in service
    assert "row.get('usage_source') == 'Committed Snapshot'" in service
    assert "'tab': workspace_tab" not in service
    assert 'default=5' in service

    assert "'object-storage-' ~ page_key ~ '-recommendations-guide'" in recommendations
    assert 'data-object-storage-analytics-recommendations' in recommendations
    assert "'object-storage-analytics-controls-readiness-' ~ page_key ~ '-guide'" in controls
    assert 'title_accessory=analytics_controls_guide' in controls
    assert 'partials/_recommendations_workspace.html' not in overview


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
        '_controls.html',
        '_recommendations_workspace.html',
        '_forecast_analysis.html',
        '_forecast_worker_status.html',
        '_bucket_forecasts.html',
        '_bucket_forecast_table.html',
        '_trend.html',
    ):
        jinja.from_string(read(f'{PARTIALS}/{filename}'))
    jinja.from_string(read('app/templates/analytics/components/_controls_readiness.html'))
