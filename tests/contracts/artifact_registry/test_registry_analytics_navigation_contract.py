from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_artifact_registry_workspace_exposes_complete_review_surface() -> None:
    navigation = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    for capability in (
        "'artifact_registry.overview'",
        "'artifact_registry.inventory'",
        "'artifact_registry.security'",
        "'artifact_registry.runtime'",
        "'artifact_registry.governance'",
        "'artifact_registry.analytics'",
    ):
        assert capability in navigation
    for route in (
        'def overview()',
        'def inventory()',
        'def security()',
        'def runtime()',
        'def governance()',
        'def analytics()',
    ):
        assert route in routes


def test_artifact_registry_routes_keep_artifact_registry_sidebar_active() -> None:
    navigation = (ROOT / 'app/common/workspace_navigation.py').read_text()

    assert "if endpoint.startswith('artifact_registry.'):" in navigation
    assert "'artifact_registry': 'overview'" in navigation
    for endpoint, capability in (
        ('artifact_registry.inventory', 'inventory'),
        ('artifact_registry.security', 'security'),
        ('artifact_registry.runtime', 'runtime'),
        ('artifact_registry.governance', 'governance'),
        ('artifact_registry.analytics', 'analytics'),
    ):
        assert f"('{endpoint}', '{capability}')" in navigation


def test_registry_analytics_has_eight_authorized_page_level_views() -> None:
    catalog = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    navigation = (ROOT / 'app/common/workspace_navigation.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    shell = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()

    views = catalog.split("'artifact_registry_analytics': (", 1)[1].split(
        "    'artifact_registry_security': (", 1
    )[0]
    expected = (
        ('overview', 'artifact_registry.analytics'),
        ('growth', 'artifact_registry.analytics_growth'),
        ('capacity', 'artifact_registry.analytics_capacity'),
        ('usage', 'artifact_registry.analytics_usage'),
        ('risk', 'artifact_registry.analytics_risk'),
        ('governance', 'artifact_registry.analytics_governance'),
        ('alerts', 'artifact_registry.analytics_alerts'),
        ('insights', 'artifact_registry.analytics_insights'),
    )
    assert views.count('CapabilityViewDefinition(') == 8
    for key, endpoint in expected:
        assert f"CapabilityViewDefinition('{key}'," in views
        assert f"'{endpoint}'" in views
        assert "('artifact_registry.view',)" in views
        if key != 'overview':
            assert f"'artifact_registry.analytics_{key}': '{key}'" in navigation
            assert f"def analytics_{key}() -> ResponseReturnValue:" in routes
            assert f"return _render_registry_analytics_page('{key}')" in routes
            assert f"'artifact_registry.analytics_{key}'" in shell

    assert "if endpoint.startswith('artifact_registry.analytics'):" in navigation
    assert "return 'artifact_registry_analytics'" in navigation
    assert "'artifact_registry_analytics': 'Analytics'" in navigation
    assert "'artifact_registry.analytics_alerts_table': 'alerts'" in navigation
    assert "def analytics() -> ResponseReturnValue:" in routes
    assert "return _render_registry_analytics_page('overview')" in routes
    assert "framed_workspace_tabs.render_navigation" not in shell
    assert "components/framed_workspace_tabs.html" not in shell
    assert "analytics.active_tab == 'overview'" in shell
    assert "section='summary'" in shell
    assert "section=analytics.active_tab" in shell
    assert 'hx-trigger="load"' in shell
    assert 'artifact-registry-analytics-active-section' in shell
    assert 'artifact-registry-analytics-summary' in shell
    assert "url_for('intelligence.recommendations', domain='registry')" in shell


def test_registry_analytics_legacy_links_redirect_and_preserve_alert_filters() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_analytics.py').read_text()
    sections = (ROOT / 'app/templates/artifact_registry/partials/_analytics_section.html').read_text()

    assert "_REGISTRY_ANALYTICS_DETAIL_ROUTES = {" in routes
    for key in ('growth', 'capacity', 'usage', 'risk', 'governance', 'alerts', 'insights'):
        assert f"'{key}': 'artifact_registry.analytics_{key}'" in routes
    assert "legacy_tab = request.args.get('tab', '', type=str)" in routes
    assert "if legacy_tab in _REGISTRY_ANALYTICS_DETAIL_ROUTES:" in routes
    assert "return redirect(url_for(_REGISTRY_ANALYTICS_DETAIL_ROUTES[legacy_tab], **alert_args))" in routes
    for field in ('alert_q', 'alert_severity', 'alert_state', 'alert_source', 'alert_page', 'alert_per_page'):
        assert f"'{field}'" in routes
    assert "return redirect(url_for('artifact_registry.analytics_alerts', **query_args))" in routes
    assert "'artifact_registry.analytics_alerts'," in routes
    assert "def analytics_alerts_table() -> ResponseReturnValue:" in routes
    assert "def build_analytics_shell(" in presentation
    assert "active_tab: str = 'overview'" in presentation
    assert "_REGISTRY_ANALYTICS_PAGE_DETAILS = {" in presentation
    assert "normalized_tab = active_tab if active_tab in _REGISTRY_ANALYTICS_PAGE_DETAILS else 'overview'" in presentation
    assert "RegistryAnalyticsSnapshot.query" in presentation
    assert "MetricsConsumer" not in presentation
    assert "url_for('artifact_registry.analytics_alerts_table')" in sections
    assert '[5, 10, 25, 50]' in sections


def test_analytics_overview_uses_shared_intro_and_level_three_navigation() -> None:
    from jinja2 import Environment

    summary = (ROOT / 'app/templates/artifact_registry/partials/_analytics_summary.html').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/analytics.html').read_text()
    Environment().parse(summary)
    Environment().parse(workspace)

    assert '{% import "components/section_intro.html" as section_intro %}' in summary
    assert "section_intro.render('Registry Analytical Posture'," in summary
    assert 'artifact-registry-analytics-summary-heading' in summary
    assert 'Analytics Summary</p>' not in summary
    assert 'for card in analytics.summary_cards' in summary
    assert "section_card.render(" in summary
    assert "'Analytical Evidence Summary'" in summary
    assert "body_classes='p-0'" in summary
    assert "posture_grid.render(analytical_metrics, columns=4, status_labels=analytical_statuses)" in summary
    for expression in ('card.icon', 'card.label', 'card.value', 'card.detail', 'card.tone'):
        assert expression in summary
    assert "analytical_statuses.append('Review' if card.tone == 'warning'" in summary
    assert "'Unavailable' if card.tone == 'unknown' else 'Ready'" in summary
    assert 'rounded-xl border border-outline-default bg-surface-card p-4 shadow-sm' not in summary

    # Navigation belongs to shared layout level-3 tabs, never an inner card.
    assert 'framed_workspace_tabs.render_navigation' not in workspace
    assert "analytics.active_tab == 'overview'" in workspace
    assert "section='summary'" in workspace
    assert "section_intro.render('Explore Analytics'," in workspace
    assert 'hx-trigger="load"' in workspace
    assert "'artifact_registry.analytics_insights'" in workspace
