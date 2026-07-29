from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "app/templates/analytics/forecast/partials/_forecast_section.html"
SCRIPT = ROOT / "app/static/js/analytics_forecast.js"


def test_capacity_posture_explains_graph_and_recommended_action():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert "How To Read The Graph" in source
    assert "Recommended Action" in source
    assert "solid line for observed utilization" in source
    assert "dashed line for projection" in source
    assert "before the critical ETA" in source
    assert "before the warning ETA" in source
    assert "No immediate capacity change is required" in source


def test_guidance_is_inside_each_resource_forecast_loop():
    source = TEMPLATE.read_text(encoding="utf-8")

    loop_start = source.index("{% for resource_key, resource_label, resource_icon in resource_tabs[:4] %}")
    trend_start = source.index('id="forecast-content-panel-trend"')
    resource_section = source[loop_start:trend_start]

    assert "How To Read The Graph" in resource_section
    assert "Recommended Action" in resource_section
    assert "forecast_payload.chart.warning_threshold" in resource_section
    assert "forecast_payload.chart.critical_threshold" in resource_section


def test_chart_legends_add_explicit_marker_to_text_gap():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function buildLegendLabelsWithTextGap(chart)" in source
    assert "text: `\\u00A0\\u00A0${label.text}`" in source
    assert source.count("generateLabels: buildLegendLabelsWithTextGap") == 2
    assert source.count("boxWidth: 14") >= 2
    assert source.count("boxHeight: 10") >= 2
