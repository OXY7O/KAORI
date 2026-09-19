from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_dashboard_and_analytics_use_distinct_recommendation_authorities() -> None:
    os_analytics = read('app/storage/object_storage/analytics/recommendations.py')
    os_dashboard = read('app/storage/object_storage/dashboard/service.py')

    assert 'get_active_recommendation_findings' not in os_analytics
    assert 'get_dashboard_recommendation_findings' in os_dashboard


def test_object_storage_overview_uses_alerts_not_recommendations() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    assert "('alerts', 'Alerts', 'bell-ring')" in overview
    assert "('recommendations', 'Recommendations'" not in overview


def test_dashboard_alert_insight_uses_canonical_labels() -> None:
    for path in (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
    ):
        source = read(path)
        assert 'Alert Intelligence' in source
        assert 'KAORI Alert Cases Available' in source
        assert 'KAORI Alert Intelligence' in source
        assert 'Top 3 Cases' not in source
