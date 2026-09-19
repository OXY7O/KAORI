from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_both_dashboards_use_central_intelligence_top_five() -> None:
    helper_path = ROOT / 'app/intelligence/dashboard_recommendations.py'
    assert helper_path.exists()
    helper = helper_path.read_text(encoding='utf-8')
    kubernetes = read('app/kubernetes/dashboard/sections/recommendations.py')
    object_storage = read('app/storage/object_storage/dashboard/service.py')

    assert 'MAX_DASHBOARD_RECOMMENDATIONS = 5' in helper
    assert "domain='kubernetes'" in kubernetes
    assert "domain='object_storage'" in object_storage
    assert 'build_recommended_actions(' not in object_storage
    assert 'get_dashboard_recommendation_findings' in kubernetes
    assert 'get_dashboard_recommendation_findings' in object_storage


def test_dashboard_recommended_actions_share_intelligence_copy_and_detail_owner() -> None:
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_recommended_actions.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_recommended_actions.html')
    canonical = 'Top active findings from the Intelligence recommendation catalog.'
    assert canonical in kubernetes
    assert canonical in object_storage
    assert 'intelligence.recommendation_details' in object_storage
    assert 'analytics.object_storage_capacity' not in object_storage
    assert 'analytics.object_storage_forecast' not in object_storage
