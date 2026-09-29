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

def test_dashboard_alert_summary_preview_is_bounded_to_five_recent_cases() -> None:
    kubernetes_template = read('app/templates/kubernetes/dashboard/partials/_alerts_summary.html')
    kubernetes_builder = read('app/kubernetes/dashboard/sections/alerts.py')
    object_template = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')
    object_service = read('app/storage/object_storage/dashboard/service.py')

    assert 'up to five recent cases' in kubernetes_template
    assert 'dashboard.alerts_snapshot.items[:5]' in kubernetes_template
    assert 'for item in raw_items[:5]' in kubernetes_builder

    assert 'up to five recent cases' in object_template
    assert 'dashboard.alerts.rows[:5]' in object_template
    assert "for case in posture['cases'][:5]" in object_service

    assert 'dashboard.alerts_snapshot.items[:3]' not in kubernetes_template
    assert 'for item in raw_items[:3]' not in kubernetes_builder
    assert 'dashboard.alerts.rows[:3]' not in object_template
    assert "for case in posture['cases'][:3]" not in object_service

