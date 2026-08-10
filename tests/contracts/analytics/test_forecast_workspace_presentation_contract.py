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


def test_forecast_hero_uses_canonical_context_card() -> None:
    content = read('app/templates/analytics/forecast/index.html')
    assert 'page_hero.context_card(' in content
    assert "('gauge', 'Highest Projection'" in content
    assert "('list-checks', 'Actionable'" in content
    assert "'Manage Clusters'" in content
    assert 'context_posture_header' not in content
    assert 'context_posture_note' not in content
    assert 'context_bottom_notice' not in content
    assert 'analytics_forecast_chart.js' in content
    assert 'analytics_forecast.js' not in content


def test_forecast_workspace_uses_capacity_surface_grammar() -> None:
    content = read('app/templates/analytics/forecast/partials/_forecast_section.html')
    assert 'analysis_surface.evidence_shell_classes()' in content
    assert 'analysis_surface.metric_grid_classes(4)' in content
    assert 'grid gap-4 lg:grid-cols-2' in content
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
    contracts = read('app/analytics/forecast/contracts.py')
    calculation = read('app/analytics/forecast/calculation.py')
    presentation = read('app/analytics/forecast/presentation.py')
    routes = read('app/analytics/forecast/routes.py')
    analytics_routes = read('app/analytics/routes.py')
    assert 'RESOURCE_OPTIONS' not in service
    assert 'moving_average' not in service
    assert "'value': 'holt_winters'" in contracts
    assert "method: str = 'holt_winters'" in calculation
    assert "'signal_quality'" in calculation
    assert "'latest_daily_average'" in calculation
    assert "'confidence':" not in calculation
    assert 'def present_forecast_materialized_context(' in presentation
    assert 'def forecast_section(' not in routes
    assert "'/forecast/section'" not in analytics_routes


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


def test_forecast_guidance_uses_white_standalone_cards() -> None:
    overview = read('app/templates/analytics/forecast/partials/_overview_methodology.html')
    section = read('app/templates/analytics/forecast/partials/_forecast_section.html')

    assert 'Forecast Operating Boundary' in overview
    assert 'analysis_surface.guidance_card_classes()' in overview
    assert 'data-kaori-forecast-boundary' in overview
    assert 'analysis_surface.guidance_fact_grid_classes(3)' in overview
    assert 'card=true' in overview
    assert 'Recommended Action' in section
    assert 'grid gap-4 lg:grid-cols-2' in section
    assert section.count('card=true') >= 2
