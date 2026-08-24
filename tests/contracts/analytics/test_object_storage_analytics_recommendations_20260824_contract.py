from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_recommendations_are_contextual_tabs_not_standalone_navigation() -> None:
    routes = read('app/storage/object_storage/analytics/routes.py')
    service = read('app/storage/object_storage/analytics/service.py')
    facade = read('app/analytics/routes.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    navigation = read('app/common/navigation.py')
    release_registry = read('scripts/release_surface_registry.py')

    assert 'def object_storage_recommendations()' in routes
    assert "query['tab'] = 'recommendations'" in routes
    assert 'redirect(' in routes
    assert "endpoint='object_storage_recommendations'" in facade
    assert "'recommendations': PageDefinition(" not in service
    assert "url_for('analytics.object_storage_recommendations')" not in menu
    assert '>Recommendations<' not in menu
    assert "'analytics.object_storage_recommendations': 'Recommendations'" not in navigation
    assert "'analytics.object_storage_recommendations'," not in release_registry


def test_every_object_storage_analytics_workspace_exposes_contextual_recommendations_tab() -> None:
    workspaces = {
        'overview': 'app/templates/storage/object_storage/analytics/partials/_overview_workspace.html',
        'capacity': 'app/templates/storage/object_storage/analytics/partials/_capacity_workspace.html',
        'performance': 'app/templates/storage/object_storage/analytics/partials/_performance_workspace.html',
        'forecast': 'app/templates/storage/object_storage/analytics/partials/_forecast_workspace.html',
        'top_consumers': 'app/templates/storage/object_storage/analytics/partials/_top_consumers_workspace.html',
        'alerts': 'app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html',
    }

    for page_key, path in workspaces.items():
        source = read(path)
        assert "('recommendations', 'Recommendations', 'list-checks')" in source, page_key
        assert 'data-analytics-tab-panel="recommendations"' in source, page_key
        assert '_recommendations_workspace.html' in source, page_key


def test_contextual_recommendations_reuse_central_intelligence_and_filter_by_page_context() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    recommendations = read('app/storage/object_storage/analytics/recommendations.py')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html')

    assert 'context.update(build_recommendation_context(system, page_key=page_key))' in service
    assert "get_active_recommendation_findings(domain='object_storage', asset_key=str(system.id))" in recommendations
    assert 'decorate_recommendation_findings' in recommendations
    assert 'def _matches_page_context(' in recommendations
    for page_key in ('overview', 'capacity', 'performance', 'forecast', 'top_consumers', 'alerts'):
        assert f"'{page_key}'" in recommendations
    assert 'recommendation_context_label' in workspace
    assert 'Intelligence owns recommendation evaluation' in workspace
    assert "url_for('intelligence.recommendation_details'" in workspace
    assert 'data-kaori-recommendation-pager' in workspace


def test_recommendation_tab_preserves_object_storage_scope_controls() -> None:
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    analytics_controls = read('app/static/js/analytics/controls.js')

    assert 'data-analytics-preserve-tab' in controls
    assert '<input type="hidden" name="tab" value="">' in controls
    assert "page_key == 'recommendations'" not in controls
    assert "url.searchParams.set('tab', tabId)" in analytics_controls
