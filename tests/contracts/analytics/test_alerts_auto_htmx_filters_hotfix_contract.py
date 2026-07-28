from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_table_filters_are_auto_htmx_without_apply_reset_buttons():
    template = read("app/templates/analytics/alerts/partials/_table_filters.html")
    assert 'hx-trigger="change delay:120ms from:select' in template
    assert "keyup changed delay:450ms" in template
    assert ">Apply<" not in template
    assert ">Reset<" not in template
    assert 'type="submit"' not in template


def test_each_table_has_local_kaori_loading_bar_and_sync_boundary():
    filters = read("app/templates/analytics/alerts/partials/_table_filters.html")
    alerts = read("app/templates/analytics/alerts/partials/_alerts_table.html")
    anomalies = read("app/templates/analytics/alerts/partials/_anomalies_table.html")
    assert 'hx-sync="{{ target_id }}:replace"' in filters
    assert "alerts-table-loading-indicator" in alerts
    assert "anomalies-table-loading-indicator" in anomalies
    assert "loading_bar.render" in alerts
    assert "loading_bar.render" in anomalies


def test_tab_and_detail_panels_have_native_hidden_fallback():
    index = read("app/templates/analytics/alerts/index.html")
    alert_row = read("app/templates/analytics/alerts/partials/_alerts_table_row.html")
    anomaly_row = read("app/templates/analytics/alerts/partials/_anomalies_table_row.html")
    assert index.count("x-bind:hidden=") >= 5
    assert 'x-bind:hidden="!expanded"' in alert_row
    assert "x-bind:hidden=\"openAnomaly !==" in anomaly_row
