from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_table_loading_bars_live_directly_below_each_table_header():
    for path, title, indicator in (
        ('app/templates/analytics/alerts/partials/_alerts_table.html', 'Active Alert Records', 'alerts-table-loading-indicator'),
        ('app/templates/analytics/alerts/partials/_anomalies_table.html', 'Detected Anomaly Candidates', 'anomalies-table-loading-indicator'),
    ):
        source = read(path)
        assert source.index(title) < source.index('loading_bar.render') < source.index('_table_filters.html')
        assert indicator in source


def test_anomaly_pagination_uses_requested_page_in_both_presenters():
    application = read('app/analytics/alerts/application.py')
    assert application.count('page=selected_page,\n        per_page=selected_anomalies_per_page,') == 2
    assert 'page=1,\n        per_page=selected_anomalies_per_page,' not in application


def test_numeric_pagination_inherits_htmx_synchronization_attributes():
    pagination_js = read('app/static/js/pagination.js')
    pagination = read('app/templates/analytics/alerts/partials/_pagination.html')
    assert "'hx-sync'" in pagination_js
    assert "'hx-on::before-request'" in pagination_js
    assert pagination.count('hx-sync="{{ target_id }}:replace"') >= 3


def test_anomaly_severity_has_no_icon_and_namespace_shows_plain_pod_context():
    row = read('app/templates/analytics/alerts/partials/_anomalies_table_row.html')
    main_row = row.split('</tr>', 1)[0]
    assert "table_label.status_label(anomaly.severity|title" in main_row
    assert 'data-lucide="alert-triangle"' not in main_row
    assert '{{ anomaly.namespace }}' in main_row
    assert '{{ anomaly.target }}' in main_row
    assert 'metadata_label(anomaly.namespace' not in main_row
    assert 'data-lucide="box"' not in main_row


def test_global_alert_controls_only_manage_cluster_and_source():
    index = read('app/templates/analytics/alerts/index.html')
    filters = read('app/templates/analytics/alerts/partials/_filters.html')
    assert 'Alert Controls &amp; Data Readiness' in filters
    assert 'Alert Source Readiness' in filters
    assert 'Latest Data Snapshot' in filters
    assert filters.count('name="cluster_id"') == 1
    assert filters.count('name="source"') == 1
    assert 'name="severity"' not in filters
    assert 'name="status"' not in filters
    assert 'name="namespace"' not in filters
    assert 'name="search"' not in filters
    assert 'keyup[' not in index
