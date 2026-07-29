from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_trend_analysis_uses_chart_and_resource_outlook_workspace() -> None:
    section = read("app/templates/analytics/forecast/partials/_forecast_section.html")
    assert "xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]" in section
    assert "Resource Outlook" in section
    assert "Projection and Warning ETA" in section
    assert "Forecast Series Legend" not in section
    assert "Historical and projected resource series" not in section


def test_each_resource_outlook_shows_warning_eta_below_projection() -> None:
    section = read("app/templates/analytics/forecast/partials/_forecast_section.html")
    trend = section.split('id="forecast-content-panel-trend"', 1)[1].split('id="forecast-content-panel-recommendations"', 1)[0]
    assert "resource_tabs[:4]" in trend
    assert "Warning ETA" in trend
    assert "item.warning_eta.label" in trend
    assert "item.warning_eta.date" in trend
    assert "item.critical_eta.label" not in trend
    assert "item.critical_eta.date" not in trend


def test_trend_chart_keeps_compact_height() -> None:
    section = read("app/templates/analytics/forecast/partials/_forecast_section.html")
    trend = section.split('id="forecast-content-panel-trend"', 1)[1].split('id="forecast-content-panel-recommendations"', 1)[0]
    assert 'h-[360px]' in trend
    assert 'h-[380px]' not in trend
