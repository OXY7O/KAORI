from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/analytics/forecast/partials/_forecast_section.html'


def test_trend_analysis_uses_compact_summary_and_balanced_workspace() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Combined Forecast' in content
    assert 'Tracked Resources' in content
    assert 'Highest Projection' in content
    assert 'xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]' in content


def test_trend_analysis_lists_projection_and_warning_eta_per_resource() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')
    trend = content.split('id="forecast-content-panel-trend"', 1)[1].split('id="forecast-content-panel-recommendations"', 1)[0]

    assert 'Resource Outlook' in trend
    assert 'item.current_percent' in trend
    assert 'item.projected_percent' in trend
    assert 'item.warning_eta.label' in trend
    assert 'item.warning_eta.date' in trend
    assert 'item.critical_eta.label' not in trend


def test_trend_analysis_preserves_chart_and_tab_fallback() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'id="forecast-trend-chart"' in content
    assert 'data-analytics-tab-panel="trend"' in content
    assert 'x-bind:hidden="activeTab !== \'trend\'"' in content
    assert 'hidden' in content
