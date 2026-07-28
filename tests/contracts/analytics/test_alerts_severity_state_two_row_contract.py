from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app' / 'templates' / 'analytics' / 'alerts' / 'partials'


def test_severity_and_state_use_separate_compact_columns() -> None:
    table = (PARTIALS / '_alerts_table.html').read_text(encoding='utf-8')
    row = (PARTIALS / '_alerts_table_row.html').read_text(encoding='utf-8')
    main_row = row.split('<div id="{{ row_key }}-details"', 1)[0]

    assert 'Severity &amp; State' not in table
    assert '>Severity</div>' in table
    assert '>State</div>' in table
    assert "table_label.status_label(alert.severity|title" in main_row
    assert "table_label.status_label(alert.status|title" in main_row


def test_both_values_remain_semantic_labels_without_icons() -> None:
    row = (PARTIALS / '_alerts_table_row.html').read_text(encoding='utf-8')
    main_row = row.split('<div id="{{ row_key }}-details"', 1)[0]

    assert 'tone=severity_tone' in main_row
    assert 'tone=status_tone' in main_row
    assert 'icon=' not in main_row.split("table_label.status_label(alert.severity|title", 1)[1].split(') }}', 1)[0]
    assert 'icon=' not in main_row.split("table_label.status_label(alert.status|title", 1)[1].split(') }}', 1)[0]
