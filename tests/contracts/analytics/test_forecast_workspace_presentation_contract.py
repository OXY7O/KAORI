from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_forecast_controls_separate_scope_and_projection_configuration() -> None:
    content = read('app/templates/analytics/forecast/partials/_controls_readiness.html')
    assert 'Scope' in content
    assert 'Projection Configuration' in content
    assert 'data-analytics-preserve-tab' in content
    assert 'name="tab"' in content
    assert 'Resource Focus' not in content
    assert 'name="resource"' not in content
    assert 'analytics_workspace.control_select_classes()' in content
    assert 'analytics_materialization' in content


def test_forecast_hero_uses_shared_metrics_and_bottom_notice() -> None:
    content = read('app/templates/analytics/forecast/index.html')
    assert "page_hero.context_metric('gauge', 'Highest Projection'" in content
    assert "page_hero.context_metric('list-checks', 'Actionable'" in content
    assert 'page_hero.context_bottom_notice(' in content
    assert 'page_hero.context_posture_note(' not in content
    assert 'analytics_forecast_chart.js' in content
    assert 'analytics_forecast.js' not in content


def test_forecast_workspace_uses_capacity_surface_grammar() -> None:
    content = read('app/templates/analytics/forecast/partials/_forecast_section.html')
    assert 'analysis_surface.evidence_shell_classes()' in content
    assert 'analysis_surface.metric_grid_classes(4)' in content
    assert 'analysis_surface.interpretation_grid_classes()' in content
    assert 'Latest Daily Average' in content
    assert 'Weekly Trend' in content
    assert 'Historical Signal Quality' in content
    assert 'Scope Boundary' in content
    assert 'Current Usage' not in content
    assert 'Growth Rate' not in content
    assert 'Confidence' not in content


def test_interactive_chart_contract_uses_tokens_and_visible_legend() -> None:
    template = read('app/templates/analytics/components/_interactive_forecast_chart.html')
    script = read('app/static/js/analytics_forecast_chart.js')
    assert 'bg-status-info' in template
    assert 'bg-kaori-primary' in template
    assert 'bg-status-normal' in template
    assert 'bg-status-warning' in template
    assert 'Historical' in template and 'Projection' in template
    assert 'legend: { display: false }' in script
    assert "cssToken('--kaori-status-info'" in script
    assert "cssToken('--kaori-brand-primary'" in script
    assert 'kaori:analytics-tab-visible' in script
    assert 'ResizeObserver' in script
    assert '#' not in '\n'.join(line for line in script.splitlines() if 'querySelector' not in line)


def test_forecast_direct_cutover_removes_legacy_assets_and_methodology() -> None:
    assert not (ROOT / 'app/static/js/analytics_forecast.js').exists()
    assert not (ROOT / 'app/templates/analytics/forecast/partials/_methodology.html').exists()
    service = read('app/analytics/forecast/service.py')
    assert 'RESOURCE_OPTIONS' not in service
    assert 'moving_average' not in service
    assert "'value': 'holt_winters'" in service
    assert "method: str = 'holt_winters'" in service
    assert "'signal_quality'" in service
    assert "'latest_daily_average'" in service
    assert "'confidence':" not in service


def test_forecast_templates_have_no_page_local_arbitrary_microcopy() -> None:
    for relative in (
        'app/templates/analytics/forecast/index.html',
        'app/templates/analytics/forecast/partials/_controls_readiness.html',
        'app/templates/analytics/forecast/partials/_overview_methodology.html',
        'app/templates/analytics/forecast/partials/_forecast_section.html',
    ):
        content = read(relative)
        assert 'text-[' not in content
        assert 'tracking-[' not in content
