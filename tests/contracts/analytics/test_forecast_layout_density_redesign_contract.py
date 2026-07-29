from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_forecast_hero_uses_standard_analytics_context_metrics() -> None:
    page = read("app/templates/analytics/forecast/index.html")
    assert "page_hero.context_metric_card_classes()" in page
    assert "Highest Projection" in page
    assert "Forecast recommendations" in page
    assert "table_label.status_label(posture_value" in page

def test_forecast_controls_fit_one_desktop_row() -> None:
    controls = read("app/templates/analytics/forecast/partials/_controls_readiness.html")
    assert "xl:grid-cols-6" in controls
    assert "2xl:grid-cols-6" not in controls

def test_resource_tabs_use_compact_summary_and_balanced_workspace() -> None:
    section = read("app/templates/analytics/forecast/partials/_forecast_section.html")
    assert "sm:grid-cols-2 xl:grid-cols-4" in section
    assert "xl:grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)]" in section
    assert "Historical observations continue into the selected projection horizon." in section
    assert "h-[300px]" in section
    assert "xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1.85fr)]" not in section

def test_chart_legend_has_space_between_marker_and_text() -> None:
    script = read("app/static/js/analytics_forecast.js")
    assert "boxWidth: 14" in script
    assert "boxHeight: 10" in script
