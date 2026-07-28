from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/analytics/forecast/partials/_forecast_section.html'


def test_trend_analysis_uses_compact_summary_strip() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Forecast Series Legend' in content
    assert 'Combined Resource Forecast' in content
    assert 'Tracked Resources' in content
    assert 'Highest Projection' in content
    assert 'overflow-hidden rounded-lg border border-outline-subtle bg-surface-hover' in content


def test_trend_analysis_lists_historical_and_forecast_per_resource() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'Historical and projected resource series' in content
    assert '<span>Historical</span>' in content
    assert '<span>Forecast</span>' in content
    assert 'border-dashed border-kaori-primary' in content
    assert 'Warning Threshold' in content
    assert 'Critical Threshold' in content


def test_trend_analysis_preserves_chart_and_tab_fallback() -> None:
    content = TEMPLATE.read_text(encoding='utf-8')

    assert 'id="forecast-trend-chart"' in content
    assert 'data-analytics-tab-panel="trend"' in content
    assert 'x-bind:hidden="activeTab !== \'trend\'"' in content
    assert 'hidden' in content
