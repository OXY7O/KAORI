from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_active_alert_table_allocates_more_width_to_alert_identity():
    table = read('app/templates/analytics/alerts/partials/_alerts_table.html')
    row = read('app/templates/analytics/alerts/partials/_alerts_table_row.html')

    assert 'col-span-4 text-xs font-semibold uppercase tracking-wide text-content-muted">Alert</div>' in table
    assert 'col-span-2 text-xs font-semibold uppercase tracking-wide text-content-muted">Scope &amp; Source</div>' in table
    assert 'class="min-w-0 lg:col-span-4"' in row
    assert 'class="min-w-0 space-y-1 lg:col-span-2"' in row


def test_active_alert_desktop_grid_still_uses_twelve_columns():
    table = read('app/templates/analytics/alerts/partials/_alerts_table.html')

    header = table.split('lg:grid">', 1)[1].split('</div>\n\n    <div class="divide-y', 1)[0]
    # Explicit counts protect the intended 4+1+1+2+2+2 allocation.
    assert header.count('col-span-4') == 1
    assert header.count('col-span-1') == 2
    assert header.count('col-span-2') == 3
