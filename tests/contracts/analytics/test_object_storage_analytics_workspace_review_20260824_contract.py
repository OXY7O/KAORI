from pathlib import Path

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
        ('Inventory is the explicit fallback when bucket metrics are absent.', buckets),
        ('Request metrics never fall back to Inventory;', buckets),
        (
            'Review S3 demand and reliability, then correlate queues, inflight work, node availability, '
            'and throughput.',
            performance,
        ),
        ('Missing evidence stays Unknown.', performance),
        ('throughput alone does not indicate health or saturation.', traffic),
        ('These are planning signals, not active alerts.', forecasts),
        ('Filters affect only these records and preserve the selected system and history window.', forecast_table),
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
    assert 'Active alerts committed from the selected provider source.' in overview_alerts
    assert 'Inflight requests indicate work, not pressure without a concurrency limit.' in performance
    assert 'Waiting requests and offline nodes determine posture.' in performance
    assert '{{ metrics_source.provider_label }} range for {{ selected_time_range }}.' in trend
    assert 'Requests and errors remain separate; traffic alone is not unhealthy.' in trend
    assert 'Request metrics never fall back to Inventory;' in buckets
    assert 'missing series, unscraped metrics, and query failure.' in buckets
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

def test_object_storage_overview_capacity_trend_is_summary_first() -> None:
    trend = read('app/templates/storage/object_storage/analytics/partials/_trend.html')
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    script = read('app/static/js/storage/object_storage/analytics.js')

    assert "page_key == 'overview' and trend_mode == 'usage'" in trend
    assert 'data-object-storage-overview-trend-summary' in trend
    assert 'analysis_surface.metric_grid_classes(4)' in trend
    assert 'analysis_surface.metric_cell_classes()' in trend
    for label, source in (
        ('Current Usage', 'metrics.usage_total_display'),
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
    assert "h-[260px] sm:h-[280px]" in trend
    assert "else 'h-[340px]'" in trend
    assert "{% elif trend_mode != 'performance' %}" in trend
    assert 'data-object-storage-trend-interpretation' in trend
    assert 'Inventory is point-in-time, not a growth forecast.' in trend
    assert "partials/_trend.html" in overview
    assert 'data-object-storage-trend-points' in trend
    assert 'data-object-storage-secondary-trend-points' in trend
    assert 'data-object-storage-projection-points' in trend
    assert 'data-object-storage-chart\\n                        role="img"' in trend
    assert 'beginAtZero: true' in script
