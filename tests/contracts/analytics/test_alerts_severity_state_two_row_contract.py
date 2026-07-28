from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROW = ROOT / 'app' / 'templates' / 'analytics' / 'alerts' / 'partials' / '_alerts_table_row.html'


def test_severity_and_alert_state_use_two_compact_data_rows() -> None:
    row = ROW.read_text(encoding='utf-8')

    assert 'class="min-w-0 space-y-1 lg:col-span-2"' in row
    assert '>Severity</p>' not in row
    assert '>Alert State</p>' not in row


def test_severity_and_state_badges_keep_independent_semantics() -> None:
    row = ROW.read_text(encoding='utf-8')

    assert 'alert.severity|title' in row
    assert 'tone=severity_tone' in row
    assert 'alert.status|title' in row
    assert 'tone=status_tone' in row
