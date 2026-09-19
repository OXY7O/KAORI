from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_dashboard_alert_summary_source_labels_stay_on_one_line_in_dedicated_row() -> None:
    templates = (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
    )
    for path in templates:
        source = read(path)
        source_block = source.split('<dt class="text-content-muted">Source</dt>', 1)[1].split('</div>', 1)[0]
        assert 'truncate' not in source_block, path
        assert 'whitespace-nowrap' in source_block, path
        assert 'data-kaori-alert-insight-metrics="dedicated-row"' in source, path
