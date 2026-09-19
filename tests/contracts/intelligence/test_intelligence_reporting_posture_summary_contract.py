from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_shared_posture_component_matches_generated_reporting_reference_grammar() -> None:
    workspace = read('app/templates/intelligence/components/_workspace.html')

    assert 'macro posture_panel(' in workspace
    assert 'data-kaori-intelligence-posture="reference-summary"' in workspace
    assert 'class="{{ table_ui.block_classes() }} {{ extra }}"' in workspace
    assert 'border-b border-outline-subtle' in workspace
    assert 'table_label.status_label(badge_text, badge_tone' in workspace
    assert 'macro posture_metric(' in workspace
    assert 'data-kaori-posture-metric' in workspace
    assert 'justify-between gap-3' in workspace
    assert 'text-kaori-primary' in workspace
    assert 'border-t border-outline-subtle' in workspace
    assert 'actions=()' in workspace


def test_every_primary_intelligence_page_uses_reference_posture_directly_below_hero() -> None:
    overview = read('app/templates/intelligence/overview.html')
    recommendations = read('app/templates/intelligence/recommendations.html')
    recommendation_summary = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    rule_catalog = read('app/templates/intelligence/rule_catalog.html')
    rule_summary = read('app/templates/intelligence/partials/_catalog_summary.html')
    alert_page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    automation = read('app/templates/intelligence/automation_control.html')

    assert overview.index('page_hero.shell_classes()') < overview.index('intelligence_ui.posture_panel(')
    assert overview.index('intelligence_ui.posture_panel(') < overview.index(
        "{% call intelligence_ui.section(\n            'Intelligence Posture'"
    )

    assert recommendations.index('page_hero.shell_classes()') < recommendations.index(
        '_recommendation_workspace_info.html'
    )
    assert 'intelligence_ui.posture_panel(' in recommendation_summary

    assert rule_catalog.index('page_hero.shell_classes()') < rule_catalog.index('catalog-summary-section')
    assert 'intelligence_ui.posture_panel(' in rule_summary

    assert alert_page.index('page_hero.shell_classes()') < alert_page.index('_alert_intelligence_summary.html')
    assert 'intelligence_ui.posture_panel(' in alert_summary

    assert automation.index('page_hero.shell_classes()') < automation.index('intelligence_ui.posture_panel(')
    assert automation.index('intelligence_ui.posture_panel(') < automation.index('Automation Control Workspace')


def test_reference_posture_keeps_four_divided_metrics_and_contextual_footer_actions() -> None:
    surfaces = (
        read('app/templates/intelligence/overview.html'),
        read('app/templates/intelligence/partials/_recommendation_workspace_info.html'),
        read('app/templates/intelligence/partials/_catalog_summary.html'),
        read('app/templates/intelligence/partials/_alert_intelligence_summary.html'),
        read('app/templates/intelligence/automation_control.html'),
    )

    for source in surfaces:
        assert 'intelligence_ui.posture_panel(' in source
        assert 'intelligence_ui.posture_metric(' in source
        assert 'grid divide-y divide-outline-subtle sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4' in source
        assert 'actions=[' in source
