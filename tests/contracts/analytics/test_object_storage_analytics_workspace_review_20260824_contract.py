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
    forecast_table = read(
        'app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html'
    )
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
    templates = '\n'.join(
        path.read_text(encoding='utf-8') for path in TEMPLATE_ROOT.rglob('*.html')
    )

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
    forecast_table = read(
        'app/templates/storage/object_storage/analytics/partials/_bucket_forecast_table.html'
    )
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')

    assert 'components/page_hero.html' in read(
        'app/templates/storage/object_storage/analytics/partials/_hero.html'
    )
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
