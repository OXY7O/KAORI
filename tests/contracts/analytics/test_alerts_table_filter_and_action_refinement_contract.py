from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates" / "analytics" / "alerts" / "partials"


def read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_firing_state_uses_semantic_label():
    source = read("_alerts_table_row.html")
    assert "table_label.status_label(alert.status|title" in source
    assert '<span class="break-words text-xs font-semibold text-content-muted">{{ alert.status|title }}</span>' not in source


def test_anomaly_action_is_right_aligned_and_uses_kaori_action_component():
    table = read("_anomalies_table.html")
    row = read("_anomalies_table_row.html")
    assert '>Action</th>' in table
    assert 'text-right' in table
    assert 'class="{{ table_ui.action_classes() }} shrink-0"' in row
    assert '<td class="px-6 py-4 align-top text-right">' in row
    assert 'rounded-full' not in row.split('@click=', 1)[1].split('</button>', 1)[0]


def test_both_tables_embed_standard_filter_toolbar():
    alerts = read("_alerts_table.html")
    anomalies = read("_anomalies_table.html")
    filters = read("_table_filters.html")
    assert '_table_filters.html' in alerts
    assert '_table_filters.html' in anomalies
    assert 'hx-sync="#alerts-page-content:replace"' in filters
    assert 'Search alert records...' in filters
    assert 'Search anomaly candidates...' in filters
    assert 'name="severity"' in filters
    assert 'name="namespace"' in filters
    assert 'name="status"' in filters
