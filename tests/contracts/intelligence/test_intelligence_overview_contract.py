from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_intelligence_root_renders_dedicated_overview() -> None:
    routes = read('app/intelligence/routes.py')

    assert "@intelligence_bp.route('/')" in routes
    assert "@permission_required('intelligence.view')" in routes
    assert 'get_intelligence_overview_payload()' in routes
    assert "render_template('intelligence/overview.html', payload=payload)" in routes
    assert "redirect(url_for('intelligence.recommendations'))" not in routes
    assert Path('app/templates/intelligence/overview.html').exists()


def test_intelligence_overview_is_committed_evidence_only() -> None:
    overview = read('app/intelligence/overview.py')

    assert 'get_active_recommendation_findings()' in overview
    assert 'INTELLIGENCE_CATALOG' in overview
    assert 'Cluster.query.count()' in overview
    assert 'ObjectStorageSystem.query.count()' in overview
    assert 'IntelligenceDecisionCandidate.query' in overview
    assert 'IntelligenceDecision.query' in overview
    assert 'KnowledgeRunbookRevision.query' in overview
    assert 'from app.intelligence.automation_control' not in overview
    for forbidden in (
        'load_alerts_by_source',
        'load_alert_stream',
        'MetricsConsumer',
        'MinioClient',
        '.query_range(',
        '.custom_query(',
    ):
        assert forbidden not in overview


def test_intelligence_overview_exposes_four_owned_capabilities() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    for title in ('Recommendations', 'Alert Intelligence', 'Rule Catalog', 'Automation Control'):
        assert f"'title': '{title}'" in overview
    assert 'payload.capabilities' in template

    for endpoint in (
        'intelligence.recommendations',
        'alert_intelligence.index',
        'intelligence.catalog',
        'automation_control.index',
    ):
        assert endpoint in overview


def test_intelligence_overview_keeps_alert_and_automation_boundaries_explicit() -> None:
    template = read('app/templates/intelligence/overview.html')

    assert 'Committed Intelligence' in template
    assert 'Provider Alert Context' in template
    assert 'Governed Automation' in template
    assert 'The Overview does not query infrastructure providers directly.' in template
    assert 'routing, grouping, silences, and inhibition remain provider-owned' in template
    assert 'Intelligence Overview never bypasses those controls.' in template


def test_intelligence_sidebar_and_welcome_enter_through_overview() -> None:
    sidebar = read('app/templates/components/navigation/intelligence_menu.html')
    welcome = read('app/welcome/shortcuts.py')
    navigation = read('app/common/navigation.py')

    overview_link = "('intelligence.index', 'layout-dashboard', 'Overview')"
    recommendations_link = "('intelligence.recommendations', 'sparkles', 'Recommendations')"
    assert overview_link in sidebar
    assert sidebar.index(overview_link) < sidebar.index(recommendations_link)
    assert "('intelligence.view', 'intelligence.index')" in welcome
    assert "'intelligence.index': 'Overview'" in navigation
    assert "endpoint.startswith(('intelligence.', 'alert_intelligence.', 'automation_control.'))" in navigation
