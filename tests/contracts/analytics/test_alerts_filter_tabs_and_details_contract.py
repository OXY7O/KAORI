from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
ALERTS = ROOT / 'app' / 'templates' / 'analytics' / 'alerts'


def _read(relative: str) -> str:
    return (ALERTS / relative).read_text(encoding='utf-8')


def test_cluster_filter_preserves_tab_workspace_and_collapses_details() -> None:
    index = _read('index.html')
    row = _read('partials/_alerts_table_row.html')
    table = _read('partials/_alerts_table.html')

    assert 'hx-push-url="true"' in index
    assert "kaori:alerts-collapse" in index
    assert 'data-alerts-tabset' in index
    assert "x-show=\"activeTab === 'alerts'\"" in index
    assert 'x-cloak' in index
    assert 'x-data="{ openAlert: null }"' not in table
    assert 'x-data="{ expanded: false }"' in row
    assert '@kaori:alerts-collapse.window="expanded = false"' in row
    assert 'x-show="expanded"' in row


def test_severity_state_matches_two_line_scope_source_pattern() -> None:
    row = _read('partials/_alerts_table_row.html')

    assert 'class="min-w-0 lg:col-span-2"' in row
    assert row.count("table_label.status_label(alert.severity|title") == 1
    assert row.count("table_label.status_label(alert.status|title") == 0
    assert '<p class="mt-1 break-words text-xs font-medium text-content-muted">{{ alert.status|title }}</p>' in row
    assert '>Severity</p>' not in row
    assert '>Alert State</p>' not in row


def test_labels_and_annotations_do_not_create_nested_vertical_scroll() -> None:
    row = _read('partials/_alerts_table_row.html')

    assert 'max-h-40' not in row
    assert 'overflow-auto' not in row
    assert 'class="mt-3 flex flex-wrap gap-1.5"' in row


def test_changed_alert_templates_parse() -> None:
    environment = Environment()
    for relative in ('index.html', 'partials/_alerts_table.html', 'partials/_alerts_table_row.html'):
        environment.parse(_read(relative))
