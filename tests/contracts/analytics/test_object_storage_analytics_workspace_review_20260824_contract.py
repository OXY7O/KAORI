from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = ROOT / 'app/templates/storage/object_storage/analytics'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_requested_object_storage_analytics_copy_is_concise_and_keeps_boundaries() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    readiness = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')
    boundary = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    capacity = read('app/templates/storage/object_storage/analytics/partials/_capacity_analysis.html')
    pressure = read('app/templates/storage/object_storage/analytics/partials/_capacity_pressure.html')
    buckets = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    performance = read('app/templates/storage/object_storage/analytics/partials/_performance_analysis.html')
    traffic = read('app/templates/storage/object_storage/analytics/partials/_performance_traffic.html')
    forecasts = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecasts.html')
    forecast_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html')
    alerts = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    materialization = read('app/storage/object_storage/analytics/materialization.py')

    expected = (
        ('Committed forecast history is solid; the linear 30-day projection is dashed.', trend),
        ('Use slope and change for direction; Inventory remains point-in-time.', trend),
        ('Full Validation checks metric families, labels, and queries for this binding.', readiness),
        ('missing time-series evidence falls back only where Inventory is explicitly supported.', boundary),
        ('Review usable capacity, consumption, headroom, and growth for the selected system.', capacity),
        ('Separate bucket governance pressure from physical capacity and spot storage concentration.', pressure),
        ('Inventory fills only supported missing bucket metrics.', buckets),
        ('Request Rate and Error Rate are metrics-only; Inventory never fills missing request or error data.', buckets),
        (
            'Review S3 demand and reliability, then correlate queues, inflight work, node availability, '
            'and throughput.',
            performance,
        ),
        ('Missing evidence stays Unknown.', performance),
        ('throughput alone does not indicate health or saturation.', traffic),
        ('These are planning signals, not active alerts.', forecasts),
        (
            'Review forecast-ready and evidence-gap buckets; filters retain the selected system and history window.',
            forecast_table,
        ),
        ('Metrics Source ALERTS provides narrower rule-state evidence.', alerts),
        ("('Stale · Failed', 'warning')", materialization),
    )
    for phrase, source in expected:
        assert phrase in source

    verbose = (
        'Historical usage comes from the committed forecasting-worker snapshot.',
        'Full Validation records whether each canonical metric family',
        'Read each value with its source role.',
        'Review usable system capacity, current consumption, remaining headroom',
        'Separate bucket-level governance pressure from physical capacity pressure',
        'Evaluate current S3 demand and request reliability first',
        'Inflight requests describe active work and are not classified as pressure',
        'Missing evidence remains unknown and is never converted into a healthy conclusion.',
        'Compare ingress and egress throughput with request and error direction.',
        'Review bucket-level usage growth, 30-day projection, quota timing',
        'Alertmanager is preferred in Automatic mode because it provides lifecycle metadata',
        'Stale · Refresh Failed',
    )
    all_sources = '\n'.join(source for _, source in expected)
    for phrase in verbose:
        assert phrase not in all_sources


def test_object_storage_analytics_visual_standard_uses_shared_tokens_and_primitives() -> None:
    templates = '\n'.join(path.read_text(encoding='utf-8') for path in TEMPLATE_ROOT.rglob('*.html'))

    for forbidden in (
        'violet-50',
        'violet-100',
        'violet-500',
        'violet-600',
        'gray-500',
        'slate-500',
        'text-[',
        'tracking-[',
        'rounded-[',
        '<style',
        'onclick=',
        'onchange=',
        'onsubmit=',
    ):
        assert forbidden not in templates

    index = read('app/templates/storage/object_storage/analytics/index.html')
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    bucket_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    forecast_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')

    assert 'components/page_hero.html' in read('app/templates/storage/object_storage/analytics/partials/_hero.html')
    assert 'components/content_tabs.html' in overview
    assert "filename='js/storage/object_storage/analytics.js'" in index
    assert '<script>' not in index
    for source in (bucket_table, forecast_table, alert_records):
        assert 'components/loading_bar.html' in source
        assert 'loading_bar.render(' in source


def test_object_storage_analytics_charts_have_accessible_names() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    forecasts = read('app/templates/storage/object_storage/analytics/partials/_bucket_forecasts.html')

    assert 'data-object-storage-chart\n                        role="img"' in trend
    assert 'aria-label="{{ ' in trend
    assert 'data-object-storage-bucket-forecast-chart\n                            role="img"' in forecasts
    assert 'aria-label="Current and projected Object Storage bucket usage chart"' in forecasts


def test_object_storage_evidence_copy_stays_compact_and_factual() -> None:
    system_detail = read('app/templates/storage/object_storage/inventory/systems/partials/_system_detail_content.html')
    system_posture = read('app/templates/storage/object_storage/inventory/systems/partials/_summary_cards.html')
    overview_alerts = read('app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html')
    performance = read('app/templates/storage/object_storage/analytics/partials/_performance_analysis.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    buckets = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    alert_summary = read('app/templates/storage/object_storage/analytics/partials/_alerts_summary.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    evidence = read('app/templates/storage/object_storage/analytics/partials/_evidence_boundary.html')
    alert_projection = read('app/storage/object_storage/analytics/alert_sources.py')

    assert 'Committed inventory; provider configuration and live health remain integration-owned.' in system_detail
    assert 'Committed alerts from the selected provider.' in overview_alerts
    assert 'Inflight reflects work; waiting requests and offline nodes indicate pressure.' in performance
    assert '{{ metrics_source.provider_label }} range for {{ selected_time_range }}.' in trend
    assert 'Requests and errors remain separate; traffic alone is not unhealthy.' in trend
    assert (
        'Request Rate and Error Rate are metrics-only; Inventory never fills missing request or error data.' in buckets
    )
    assert 'missing samples, unscraped metrics, and query failures.' in buckets
    assert 'Inventory fallback is per field and only where supported.' in buckets
    assert 'Alertmanager/Metrics Source ALERTS report provider alerts;' in alert_summary
    assert 'If either evidence family is unavailable, posture stays Unknown' in alert_summary
    assert 'Metrics Source ALERTS provides narrower rule-state evidence.' in alert_records

    assert 'Provider conditions require review.' in system_posture
    assert (
        'Provider readiness and committed inventory coverage for the active Object Storage Systems scope.'
        in system_posture
    )
    assert 'worker query succeeded but found no samples' in evidence
    assert 'missing samples are not zero usage.' in evidence
    assert 'currently reports no active alerts for this Object Storage system.' in alert_projection
    assert 'not proof of overall system health.' in alert_projection

    # Neither message rewrites provider-state logic or collapses absence into zero.
    assert "if not stream.get('connected'):" in alert_projection
    assert "status, tone = 'Unknown', 'unknown'" in alert_projection
    assert "status, tone = 'No Active Alerts', 'normal'" in alert_projection


def test_provider_alert_records_clear_filters_precedes_persistent_source_context() -> None:
    """Filtered and unfiltered headers keep one canonical DOM reading order."""
    source = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    header = source.split('<header', 1)[1].split('</header>', 1)[0]

    assert 'components/table_registry.html' in source
    assert 'components/table_primitives.html' in source
    assert header.count('registry_ui.clear_filters_action(') == 1
    assert header.index('{% if alert_filters_active %}') < header.index('registry_ui.clear_filters_action(')
    assert (
        header.index('registry_ui.clear_filters_action(')
        < header.index('{% endif %}', header.index('registry_ui.clear_filters_action('))
        < header.index('table_label.status_label(alert_source.label, alert_source.tone)')
        < header.index("table_label.metadata_label(alert_source.resolved_label ~ ' Source'")
    )
    assert "table_ui.action_classes() ~ ' h-9 px-3'" in header
    assert "target='#object-storage-alert-records'" in header
    assert "indicator='#object-storage-alert-records-loading'" in header
    assert "sync='#object-storage-alert-records:replace'" in header
    assert "tab='records'" in header
    assert 'alert_per_page=alert_table.pagination.per_page' in header
    assert "alert_table.severity != 'all'" in source
    assert "alert_table.state != 'all'" in source
    assert 'hx-target="#object-storage-alert-records"' in source


def test_object_storage_overview_capacity_trend_is_chart_centered() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    capacity = read('app/templates/storage/object_storage/analytics/partials/_overview_capacity_snapshot.html')
    health = read('app/templates/storage/object_storage/analytics/partials/_overview_analysis.html')
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    script = read('app/static/js/storage/object_storage/analytics.js')

    assert "page_key == 'overview' and trend_mode == 'usage'" in trend
    assert 'data-object-storage-capacity-compact' in capacity
    assert 'data-object-storage-capacity-facts' in capacity
    assert 'data-object-storage-capacity-utilization' in capacity
    assert 'sm:grid-cols-3' in capacity
    assert 'metrics.capacity_total_display' in capacity
    assert 'metrics.usage_total_display' in capacity
    assert 'metrics.capacity_free_display' in capacity
    assert 'metrics.utilization is not none' in capacity
    assert 'value="{{ metrics.utilization }}"' in capacity
    assert 'metrics.capacity_posture.detail' in capacity
    assert "url_for('analytics.object_storage_capacity'" in capacity
    assert 'metric_grid_classes(4)' not in capacity
    assert 'data-object-storage-overview-trend-summary' in trend
    for label, source in (
        ('Window Change', 'trend_summary.delta_display'),
        ('Growth / Day', 'trend_summary.growth_per_day_display'),
        ('Direction', 'trend_summary.direction_label'),
    ):
        assert label in trend
        assert source in trend
    panel = trend.split('{% if trend %}', 1)[1]
    assert panel.index('data-object-storage-overview-trend-summary') < panel.index(
        'data-object-storage-chart-container'
    )
    assert 'grid gap-px bg-outline-subtle sm:grid-cols-3' in trend
    assert "analysis_surface.role_icon_classes('status' if loop.last else 'brand'" in trend
    assert 'for label, value, helper, icon in compact_metrics' in trend
    assert (
        'analysis_surface.metric_grid_classes(4)' not in trend
    )  # Both Overview trends reuse three shared signal cells.
    assert 'h-[260px] sm:h-[280px]' in trend
    assert "else 'h-[340px]'" in trend
    assert 'data-object-storage-trend-interpretation' in trend
    assert 'Inventory is point-in-time, not a growth forecast.' in trend
    assert 'partials/_trend.html' in overview
    for attr in (
        'data-object-storage-trend-points',
        'data-object-storage-secondary-trend-points',
        'data-object-storage-projection-points',
        'data-object-storage-chart',
        'role="img"',
    ):
        assert attr in trend
    assert 'beginAtZero: true' in script
    assert 'components/info_tip.html' in health
    assert "variant='guide'" in health
    assert "placement='right'" in health
    assert 'metrics.operational_posture.detail' in health
    assert 'Capacity → Performance → Top Consumers → Forecast' in health
    assert 'interpretation_callout(' not in health
    assert 'interpretation_grid_classes(' not in health


def test_object_storage_overview_tab_polish_preserves_source_boundaries() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    consumers = read('app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html')
    alerts = read('app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html')

    assert 'analysis_surface.snapshot_header_icon_classes()' in trend
    assert 'compact_forecast_overview' in trend
    assert 'compact_overview_trend = compact_usage_overview or compact_forecast_overview' in trend
    assert 'data-object-storage-forecast-interpretation' in trend
    assert 'selected_forecast_history_window' in trend
    assert 'data-object-storage-projection-points' in trend
    assert 'Open Top Consumers for ranked bucket evidence and ownership.' in consumers
    assert "url_for('analytics.object_storage_top_consumers'" in consumers
    for phrase in (
        'Alertmanager owns lifecycle; metrics alerts are fallback, anomalies separate.',
        'Committed alerts from the selected provider.',
        'KAORI signals crossing monitored thresholds.',
    ):
        assert phrase in alerts
    assert 'overview_alerts.provider_alert_count' in alerts
    assert 'overview_alerts.anomaly_count' in alerts


def test_object_storage_evidence_summary_keeps_full_audit_and_unknown_states() -> None:
    workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    context = read('app/templates/storage/object_storage/analytics/partials/_overview_evidence_context.html')

    assert 'partials/_metrics_readiness.html' in workspace
    assert 'partials/_overview_evidence_context.html' in workspace
    assert 'partials/_overview_evidence_snapshot.html' not in workspace
    assert 'partials/_evidence_boundary.html' not in workspace
    assert 'data-object-storage-evidence-context' in context
    for marker in (
        'data-object-storage-evidence-authorities',
        'data-object-storage-evidence-readiness',
        'data-object-storage-evidence-coverage',
        'data-object-storage-evidence-details',
        'data-object-storage-evidence-missing-values',
        'data-object-storage-evidence-reconciliation',
    ):
        assert marker in context
    for source_field in (
        'metrics_readiness',
        'analytics_materialization',
        'inventory_observed_at',
        'forecast_materialization',
        'overview_alerts',
        'context_alert_source.resolved_label',
        'metrics_source.provider_label',
    ):
        assert source_field in context
    assert 'partials/_reconciliation.html' in context
    for state in ('Not Configured', 'No Current Samples', 'Metric Not Scraped', 'Runtime Query Failed'):
        assert state in context
    assert 'No Inventory fallback for request metrics.' in context
    assert 'Missing evidence stays Unknown' in context
    assert 'Additional Evidence Context' not in workspace


def test_object_storage_analytics_overview_headings_and_trend_description_align() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    overview_health = 'partials/_overview_analysis.html'
    overview_workspace = 'partials/_overview_workspace.html'

    posture_heading = index.index('data-object-storage-operational-posture-heading')
    workspace_heading = index.index('data-object-storage-analysis-workspaces-heading')
    assert posture_heading < index.index(overview_health)
    assert index.index(overview_health) < workspace_heading < index.index(overview_workspace)
    assert 'Operational Posture' in index
    assert 'Analysis Workspaces' in index
    assert 'Review capacity, request reliability, growth, and concentration' in index
    assert 'Explore capacity trends, request performance, consumers, forecasts' in index

    header = trend.split('<header class=', 1)[1].split('</header>', 1)[0]
    assert 'flex min-w-0 items-start gap-3' in header
    assert header.index('<h2 class=') < header.index('<p class=')
    title_container = header.split('<div class="min-w-0">', 1)[1]
    assert '<h2 class=' in title_container
    assert '<p class=' in title_container
    assert 'Storage Usage Trend' in title_container
    assert 'data-object-storage-overview-trend-summary' in trend
    assert 'bg-surface-card p-4 sm:p-5' in trend
    assert 'sm:grid-cols-3' in trend
    assert 'compact_forecast_overview' in trend


def test_object_storage_analysis_workspace_intros_follow_overview_section_standard() -> None:
    index = read('app/templates/storage/object_storage/analytics/index.html')

    # Parse the actual composed template, not a hand-written substitute.
    Environment().parse(index)
    gate = "page_key in ['capacity', 'performance', 'forecast', 'top_consumers', 'alerts']"
    heading = 'data-object-storage-domain-analysis-heading="{{ page_key }}"'
    assert gate in index
    assert index.count('data-object-storage-domain-analysis-heading') == 1
    assert index.index('partials/_controls.html') < index.index(heading)
    assert index.index(heading) < index.index("{% if page_key == 'overview' %}")
    assert 'analysis_intros[page_key]' in index

    intro = index.split(heading, 1)[1].split('</div>', 1)[0]
    assert '<h2 class="text-base font-semibold text-content-primary">{{ analysis_intro[0] }}</h2>' in intro
    assert '<p class="text-sm leading-6 text-content-secondary">{{ analysis_intro[1] }}</p>' in intro
    assert index.count('data-object-storage-operational-posture-heading') == 1
    assert index.count('data-object-storage-analysis-workspaces-heading') == 1

    expected = (
        (
            'capacity',
            'Capacity & Usage Analysis',
            'Review physical headroom, usage trends, bucket quotas, and committed evidence.',
        ),
        (
            'performance',
            'Performance Analysis',
            'Review request reliability, traffic direction, and bucket activity from committed evidence.',
        ),
        (
            'forecast',
            'Forecast Analysis',
            'Review projected usage, bucket forecasts, and worker-committed planning evidence.',
        ),
        (
            'top_consumers',
            'Top Consumers Analysis',
            'Review storage concentration, request activity, and bucket ownership.',
        ),
        (
            'alerts',
            'Alerts & Anomalies Analysis',
            'Review provider alert lifecycles and KAORI anomaly signals separately.',
        ),
    )
    for key, title, description in expected:
        assert f"'{key}': ('{title}', '{description}')" in index
        assert f"{{% elif page_key == '{key}' %}}" in index


def test_object_storage_overview_consumer_reading_is_compact_and_unknown_safe() -> None:
    consumers = read('app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html')

    assert "'Top bucket holds '" in consumers
    assert "' of known usage.'" in consumers
    assert "'No bucket usage evidence available.'" in consumers
    assert 'concentration_reading' in consumers
    assert 'whitespace-nowrap' not in consumers
    assert "url_for('analytics.object_storage_top_consumers'" in consumers


def test_object_storage_forecast_uses_capacity_v2_summary_and_distinct_history() -> None:
    forecast = read('app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')

    assert 'data-object-storage-forecast-compact' in forecast
    assert 'data-object-storage-forecast-facts' in forecast
    assert 'data-object-storage-forecast-baseline' in forecast
    assert 'grid gap-x-8 gap-y-5 sm:grid-cols-3' in forecast
    assert 'metric_grid_classes(4)' not in forecast
    for field in (
        'metrics.forecast_display.projected_7d',
        'metrics.forecast_display.projected_30d',
        'metrics.forecast_display.days_to_capacity',
        'metrics.forecast_display.growth_per_day',
        'forecast_materialization.label',
        'forecast_materialization.tone',
        'metrics.forecast_posture.detail',
    ):
        assert field in forecast
    assert 'object_storage_trend_mode = "forecast"' in forecast
    assert "url_for('analytics.object_storage_forecast'" in forecast
    assert 'Historical Growth / Day' in trend
    assert 'trend_summary.growth_per_day_display' in trend
    assert 'data-object-storage-projection-points' in trend
    assert 'data-object-storage-forecast-interpretation' in trend
    assert 'compact_overview_trend' in trend
    assert 'sm:grid-cols-3' in trend
    assert 'partials/_overview_forecast_snapshot.html' in workspace


def test_object_storage_evidence_shows_full_contract_as_primary_content() -> None:
    workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')

    primary_contract = workspace.index('partials/_metrics_readiness.html')
    unified_context = workspace.index('partials/_overview_evidence_context.html')
    assert primary_contract < unified_context
    context = read('app/templates/storage/object_storage/analytics/partials/_overview_evidence_context.html')
    assert context.count('<details') == 2
    assert 'data-object-storage-evidence-details' in context
    assert 'data-object-storage-evidence-reconciliation' in context
    assert 'partials/_reconciliation.html' in context


def test_object_storage_analytics_templates_compile_before_http_render() -> None:
    jinja = Environment()
    for relative in (
        'app/templates/storage/object_storage/analytics/index.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_workspace.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_trend.html',
    ):
        jinja.parse(read(relative))

    # Flask's 500 originated during Jinja compilation, not from committed metrics.
    jinja.from_string(read('app/templates/storage/object_storage/analytics/partials/_trend.html'))


def test_object_storage_overview_guides_and_performance_family_parity() -> None:
    workspace = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    performance = read('app/templates/storage/object_storage/analytics/partials/_overview_performance_snapshot.html')
    consumers = read('app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html')
    alerts = read('app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html')
    forecast = read('app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')

    targets = (
        (workspace, 'object-storage-analytics-overview-workspace-guide'),
        (performance, 'object-storage-request-path-snapshot-guide'),
        (consumers, 'object-storage-consumer-concentration-snapshot-guide'),
        (forecast, 'object-storage-forecast-snapshot-guide'),
        (trend, 'object-storage-overview-forecast-trend-guide'),
        (alerts, 'object-storage-provider-alerts-anomaly-snapshot-guide'),
    )
    for source, tip_id in targets:
        assert 'components/info_tip.html' in source
        assert 'info_tip.render(' in source
        assert tip_id in source
        assert "variant='guide'" in source
        assert "placement='right'" in source
    assert '{% elif compact_forecast_overview %}' in trend

    for partial in (performance, consumers, alerts):
        assert 'analysis_surface.snapshot_shell_classes()' in partial
        assert 'analysis_surface.metric_grid_classes(4)' in partial
        assert 'analysis_surface.metric_cell_classes()' in partial
        assert 'analysis_surface.metric_icon_classes(' in partial
        assert 'border-t border-outline-subtle px-5 py-4 sm:px-6' in partial
        assert 'bg-kaori-primary px-4' in partial
        assert 'items-center sm:justify-between' in partial

    assert 'analysis_surface.interpretation_grid_classes()' not in consumers
    assert 'analysis_surface.interpretation_callout(' not in consumers
    assert 'concentration_reading' in consumers
    assert 'No bucket usage evidence available.' in consumers
    assert 'overview_alerts.evidence_available' in alerts
    assert 'overview_alerts.degraded' in alerts
    assert 'source.resolved_label' in alerts
    assert 'overview_alerts.anomaly_count' in alerts


def test_object_storage_overview_modified_templates_pass_jinja_parser() -> None:
    jinja = Environment()
    jinja.filters['user_datetime'] = lambda value, fallback=None: value or fallback
    paths = (
        'app/templates/storage/object_storage/analytics/partials/_overview_workspace.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_performance_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_consumer_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_alerts_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_forecast_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_trend.html',
        'app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_capacity_snapshot.html',
        'app/templates/storage/object_storage/analytics/partials/_overview_evidence_context.html',
    )
    for path in paths:
        jinja.from_string(read(path))


def test_object_storage_overview_capacity_and_contract_guides() -> None:
    capacity = read('app/templates/storage/object_storage/analytics/partials/_overview_capacity_snapshot.html')
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    contract = read('app/templates/storage/object_storage/analytics/partials/_metrics_readiness.html')

    for source, guide_id in (
        (capacity, 'object-storage-capacity-snapshot-guide'),
        (trend, 'object-storage-overview-usage-trend-guide'),
        (contract, 'object-storage-operational-metrics-contract-guide'),
    ):
        assert 'components/info_tip.html' in source
        assert guide_id in source
        assert "variant='guide'" in source
        assert "placement='right'" in source
    assert '{% if compact_usage_overview %}' in trend
    assert '{% elif compact_forecast_overview %}' in trend
    assert 'object-storage-overview-forecast-trend-guide' in trend
