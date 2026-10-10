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


def test_analytics_summary_uses_shared_intro_without_changing_seven_domain_tabs() -> None:
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

    # The seven-domain Analytics navigation is intentionally framed and
    # server owned; the two-view Governance/Supply Chain use content tabs.
    assert 'framed_workspace_tabs.render_navigation' in workspace
    assert "section='summary'" in workspace
    assert 'hx-trigger="load"' in workspace
