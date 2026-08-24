from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_dashboard_family_reads_recommendation_origin_alert_cases_from_alert_intelligence() -> None:
    shared = read('app/intelligence/alert_intelligence/dashboard_cases.py')
    kubernetes = read('app/kubernetes/dashboard/service.py')
    object_storage = read('app/storage/object_storage/dashboard/service.py')

    assert 'def active_recommendation_alert_cases(' in shared
    assert "AlertCase.source_type == 'recommendation'" in shared
    assert "AlertCase.source_state.in_(('firing', 'unknown'))" in shared
    assert "AlertCase.workflow_state != 'closed'" in shared

    assert 'active_recommendation_alert_cases' in kubernetes
    assert "domain='kubernetes'" in kubernetes
    assert 'def _kaori_alert_snapshot(' in kubernetes
    assert 'dashboard.alerts_snapshot, _ = _alerts_signal(selected)' not in kubernetes

    assert 'active_recommendation_alert_cases' in object_storage
    assert "domain='object_storage'" in object_storage
    assert "AlertCase.source_type == 'recommendation'" not in object_storage


def test_dashboard_family_explains_kaori_alert_intelligence_as_primary_alert_source() -> None:
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_alerts_summary.html')
    kubernetes_guidance = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')
    object_storage_guidance = read(
        'app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html'
    )

    for content in (kubernetes, object_storage):
        assert 'KAORI Alert Intelligence' in content
        assert 'recommendation-origin' in content.lower()

    for content in (kubernetes_guidance, object_storage_guidance):
        assert 'KAORI Alert Intelligence' in content
        assert 'Raw source alerts remain in Analytics' in content

    assert 'Active Alertmanager and Metrics Source alert signals.' not in kubernetes
    assert "action_href=url_for('alert_intelligence.index'" in kubernetes
    assert "action_href=url_for('alert_intelligence.index'" in object_storage


def test_dashboard_freshness_keeps_raw_alert_source_readiness_separate() -> None:
    kubernetes = read('app/kubernetes/dashboard/service.py')
    object_storage = read('app/storage/object_storage/dashboard/service.py')

    assert "if section == 'data_freshness':" in kubernetes
    assert 'dashboard.alerts_snapshot, alerts_result = _alerts_signal(selected)' in kubernetes
    assert "'label': 'Alert Evidence'" in object_storage
    assert 'Alertmanager preferred with Metrics Source fallback' in object_storage
