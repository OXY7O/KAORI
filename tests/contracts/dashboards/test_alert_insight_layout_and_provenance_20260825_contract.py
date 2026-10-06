from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_alert_insight_uses_full_width_header_then_dedicated_metric_row() -> None:
    shared = read('app/templates/components/operational_alert_summary.html')
    for token in (
        'data-kaori-alert-insight="stacked"',
        'data-kaori-alert-insight-metrics="dedicated-row"',
        'sm:grid-cols-[7rem_9rem_minmax(12rem,1fr)]',
    ):
        assert token in shared
    source_metric = shared.split('<dt class="text-content-muted">Source</dt>', 1)[1].split('</div>', 1)[0]
    assert 'whitespace-nowrap' in source_metric

    for path in (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
        'app/templates/artifact_registry/partials/_overview_alerts_summary.html',
    ):
        source = read(path)
        assert 'components/operational_alert_summary.html' in source
        assert 'alert_summary.render(' in source


def test_alert_insight_highest_value_uses_semantic_severity_color() -> None:
    shared = read('app/templates/components/operational_alert_summary.html')
    highest = shared.split('<dt class="text-content-muted">Highest</dt>', 1)[1].split('</div>', 1)[0]
    for token in (
        'text-status-critical-text',
        'text-status-warning-text',
        'text-status-info-text',
        'text-status-normal-text',
    ):
        assert token in highest


def test_dashboard_alert_response_footer_reports_data_owner_not_internal_promotion_detail() -> None:
    shared = read('app/templates/components/operational_alert_response.html')
    for token in (
        'operational_callout.render(',
        "source_title='Alert Data Source'",
        "source_description='KAORI Alert Intelligence · Active AlertCase records.'",
        "icon='brain-circuit'",
        "tone='info'",
        "variant='semantic'",
    ):
        assert token in shared
    assert 'Recommendation-origin durable alert cases' not in shared
    assert 'Raw source alerts remain in Analytics' not in shared

    for path in (
        'app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html',
        'app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html',
    ):
        assert 'components/operational_alert_response.html' in read(path)
