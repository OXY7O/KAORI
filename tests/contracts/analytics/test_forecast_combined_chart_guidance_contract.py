from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/analytics/forecast/partials/_forecast_section.html'


def test_combined_forecast_has_guidance_below_chart() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')
    trend = content.split('id="forecast-content-panel-trend"', 1)[1].split(
        'id="forecast-content-panel-recommendations"', 1
    )[0]

    canvas_index = trend.index('id="forecast-trend-chart"')
    guidance_index = trend.index('How To Read The Combined Forecast')

    assert guidance_index > canvas_index
    assert 'What To Do' in trend
    assert 'Resource Outlook panel' in trend
    assert 'forecast_payload.chart.warning_threshold|default(75)' in trend
    assert 'nearest Warning ETA' in trend


def test_combined_forecast_guidance_uses_compact_two_column_layout() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')
    trend = content.split('id="forecast-content-panel-trend"', 1)[1].split(
        'id="forecast-content-panel-recommendations"', 1
    )[0]

    assert 'grid border-t border-outline-subtle bg-surface-card/60 lg:grid-cols-2' in trend
    assert 'lg:border-l lg:border-t-0' in trend
