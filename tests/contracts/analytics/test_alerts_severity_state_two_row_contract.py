from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROW = ROOT / 'app' / 'templates' / 'analytics' / 'alerts' / 'partials' / '_alerts_table_row.html'


def test_severity_and_alert_state_use_two_compact_rows() -> None:
    row = ROW.read_text(encoding='utf-8')

    assert 'class="min-w-0 lg:col-span-2"' in row
    assert "table_label.status_label(alert.severity|title" in row
    assert '<p class="mt-1 break-words text-xs font-medium text-content-muted">{{ alert.status|title }}</p>' in row


def test_state_row_is_plain_text_without_an_icon_or_second_badge() -> None:
    row = ROW.read_text(encoding='utf-8')
    main_row = row.split('<div id="{{ row_key }}-details"', 1)[0]

    assert "tone=severity_tone" in main_row
    assert "table_label.status_label(alert.status|title" not in main_row
    assert 'data-lucide="activity"' not in main_row
