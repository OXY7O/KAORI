from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALERTS_PARTIALS = ROOT / 'app/templates/analytics/kubernetes/alerts/partials'


def test_active_alert_state_follows_scope_and_source_in_header_and_row() -> None:
    table = (ALERTS_PARTIALS / '_alerts_table.html').read_text(encoding='utf-8')
    row = (ALERTS_PARTIALS / '_alerts_table_row.html').read_text(encoding='utf-8')
    main_row = row.split('<div id="{{ row_key }}-details"', 1)[0]

    assert table.index("evidence_list.header_cell('Scope & Source'") < table.index("evidence_list.header_cell('State'")
    assert main_row.index('{{ alert.namespace }}') < main_row.index('alert.status|title')


def test_semantic_table_headers_use_global_display_capital_standard() -> None:
    source_css = (ROOT / 'frontend/styles.css').read_text(encoding='utf-8')

    assert 'thead th {' in source_css
    assert 'text-transform: uppercase;' in source_css
