from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SECTION_TEMPLATE = ROOT / 'app/templates/analytics/forecast/partials/_forecast_section.html'
FORECAST_JS = ROOT / 'app/static/js/analytics_forecast.js'


def test_resource_forecast_section_contains_per_resource_canvases() -> None:
    content = SECTION_TEMPLATE.read_text(encoding='utf-8')

    assert 'forecast-resource-chart-{{ resource_key }}' in content
    assert 'data-forecast-resource-canvas="true"' in content
    assert 'Observed vs projected utilization' in content
    assert 'resource_tabs[:4]' in content
    assert '<span>Historical</span>' in content
    assert '<span>Forecast</span>' in content


def test_trend_analysis_contains_expanded_forecast_legend() -> None:
    content = SECTION_TEMPLATE.read_text(encoding='utf-8')

    assert 'forecast-trend-chart-data' in content
    assert 'Critical Threshold' in content
    assert 'Warning Threshold' in content
    assert 'Historical and projected resource series' in content
    assert 'border-dashed border-kaori-primary' in content


def test_forecast_javascript_renders_resource_and_trend_charts() -> None:
    content = FORECAST_JS.read_text(encoding='utf-8')

    assert 'renderResourceForecastCharts' in content
    assert 'renderTrendForecastChart' in content
    assert 'forecast-resource-canvas' in content
    assert 'forecast-trend-chart' in content
