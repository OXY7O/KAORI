from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_analytics_exposes_recommendations_as_central_intelligence_projection() -> None:
    routes = read('app/storage/object_storage/analytics/routes.py')
    service = read('app/storage/object_storage/analytics/service.py')
    recommendations = read('app/storage/object_storage/analytics/recommendations.py')
    facade = read('app/analytics/routes.py')
    index = read('app/templates/storage/object_storage/analytics/index.html')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    navigation = read('app/common/navigation.py')

    assert 'def object_storage_recommendations()' in routes
    assert "return _render('recommendations')" in routes
    assert "endpoint='object_storage_recommendations'" in facade
    assert "'/object-storage/recommendations'" in facade
    assert "'recommendations': PageDefinition(" in service
    assert "page_key == 'recommendations'" in service
    assert 'build_recommendation_context(system)' in service
    assert "get_active_recommendation_findings(domain='object_storage', asset_key=str(system.id))" in recommendations
    assert 'decorate_recommendation_findings' in recommendations
    assert 'build_object_storage_recommendation_findings' not in recommendations
    assert "page_key == 'recommendations'" in index
    assert '_recommendations_workspace.html' in index
    assert "url_for('analytics.object_storage_recommendations')" in menu
    assert '>Recommendations<' in menu
    assert "'analytics.object_storage_recommendations': 'Recommendations'" in navigation


def test_object_storage_analytics_recommendations_are_read_only_and_inventory_scoped() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html')
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')

    assert "if page_key == 'recommendations':" in service
    assert 'inventory_required_blocker(system)' in service
    assert 'context.update(build_recommendation_context(system))' in service
    assert 'Intelligence owns recommendation evaluation' in workspace
    assert "url_for('intelligence.recommendation_details'" in workspace
    assert 'data-kaori-recommendation-pager' in workspace
    assert "page_key == 'recommendations'" in controls
    assert 'Metrics Source and alert-provider queries' not in workspace


def test_object_storage_analytics_route_permission_and_documentation_include_recommendations() -> None:
    routes = read('app/storage/object_storage/analytics/routes.py')
    audit = read('tests/contracts/analytics/test_object_storage_analytics_audit_20260815_contract.py')
    docs = read('app/intelligence/README.md')

    assert routes.count("@permission_required('object_storage_analytics.view')") == 10
    assert '== 10' in audit
    assert 'Object Storage Analytics recommendation tabs consume the same Intelligence finding source' in docs
    assert 'Future Object Storage Analytics recommendation tabs' not in docs
