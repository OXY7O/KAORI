from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_object_storage_recommendations_are_contextual_tabs_not_standalone_navigation() -> None:
    routes = read('app/storage/object_storage/analytics/routes.py')
    service = read('app/storage/object_storage/analytics/service.py')
    menu = read('app/templates/components/navigation/analytics_menu.html')
    navigation = read('app/common/navigation.py')
    release_registry = read('scripts/release_surface_registry.py')

    assert 'def object_storage_recommendations()' in routes
    assert 'redirect(' in routes
    assert 'urlencode(params)' in routes
    assert "url_for('intelligence.recommendations')" in routes
    assert "'recommendations': PageDefinition(" not in service
    assert "url_for('analytics.object_storage_recommendations')" not in menu
    assert '>Recommendations<' not in menu
    assert "'analytics.object_storage_recommendations': 'Recommendations'" not in navigation
    assert "'analytics.object_storage_recommendations'," not in release_registry


def test_object_storage_overview_uses_alerts_while_analysis_pages_expose_recommendations() -> None:
    overview = read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')
    assert "('alerts', 'Alerts', 'bell-ring')" in overview
    assert "('recommendations', 'Recommendations', 'list-checks')" not in overview

    workspaces = {
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


def test_contextual_recommendations_are_analytics_local_evidence_guidance() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    recommendations = read('app/storage/object_storage/analytics/recommendations.py')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_recommendations_workspace.html')
    hero = read('app/templates/storage/object_storage/analytics/partials/_hero.html')
    hero_posture = read('app/templates/storage/object_storage/analytics/partials/_hero_posture.html')

    assert 'get_active_recommendation_findings' not in recommendations
    assert 'decorate_recommendation_findings' not in recommendations
    for builder in (
        'build_capacity_recommendations',
        'build_performance_recommendations',
        'build_forecast_recommendations',
        'build_top_consumer_recommendations',
        'build_alert_recommendations',
    ):
        assert f'def {builder}(' in recommendations
    assert "apply_recommendation_context(context, page_key='alerts')" in service
    assert 'apply_recommendation_context(context, page_key=page_key)' in service
    assert 'Central Intelligence' not in workspace
    assert "page_key == 'recommendations'" not in hero
    assert "page_key == 'recommendations'" not in hero_posture
    assert 'Central Intelligence Findings' not in hero
    assert 'Central Intelligence findings for this system' not in hero_posture
    assert 'intelligence.recommendation_details' not in workspace
    assert 'Derived From:' in workspace
    assert 'data-kaori-recommendation-pager' in workspace


def test_recommendation_tab_preserves_object_storage_scope_controls() -> None:
    controls = read('app/templates/storage/object_storage/analytics/partials/_controls.html')
    analytics_controls = read('app/static/js/analytics/controls.js')

    assert 'data-analytics-preserve-tab' in controls
    assert '<input type="hidden" name="tab" value="">' in controls
    assert "url.searchParams.set('tab', tabId)" in analytics_controls
