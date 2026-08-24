from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alert_insight_uses_full_width_header_then_dedicated_metric_row() -> None:
    templates = (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
    )
    for path in templates:
        source = read(path)
        assert 'data-kaori-alert-insight="stacked"' in source, path
        assert 'data-kaori-alert-insight-metrics="dedicated-row"' in source, path
        assert 'sm:grid-cols-[7rem_9rem_minmax(12rem,1fr)]' in source, path
        source_metric = source.split('<dt class="text-content-muted">Source</dt>', 1)[1].split('</div>', 1)[0]
        assert 'whitespace-nowrap' in source_metric


def test_alert_insight_highest_value_uses_semantic_severity_color_in_both_domains() -> None:
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_alerts_summary.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')
    expected = (
        'text-status-critical-text',
        'text-status-warning-text',
        'text-status-info-text',
        'text-status-normal-text',
    )
    for source in (kubernetes, object_storage):
        highest = source.split('<dt class="text-content-muted">Highest</dt>', 1)[1].split('</div>', 1)[0]
        for token in expected:
            assert token in highest


def test_dashboard_alert_response_footer_reports_data_owner_not_internal_promotion_detail() -> None:
    templates = (
        'app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html',
        'app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html',
    )
    for path in templates:
        source = read(path)
        assert 'operational_callout.render(' in source, path
        assert "'Alert Data Source'" in source, path
        assert "'KAORI Alert Intelligence · Active AlertCase records.'" in source, path
        assert "icon='brain-circuit'" in source, path
        assert "tone='info'" in source, path
        assert "variant='semantic'" in source, path
        assert 'Recommendation-origin durable alert cases' not in source, path
        assert 'Raw source alerts remain in Analytics' not in source, path
