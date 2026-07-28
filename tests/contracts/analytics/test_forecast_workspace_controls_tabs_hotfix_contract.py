from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_forecast_filters_use_one_desktop_row_and_local_readiness_warning() -> None:
    controls = read("app/templates/analytics/forecast/partials/_controls_readiness.html")
    page = read("app/templates/analytics/forecast/index.html")

    assert "2xl:grid-cols-6" in controls
    assert controls.count("<select") == 6
    assert "hx-sync=\"#forecast-page:replace\"" in controls
    assert "Forecast Snapshot Available · Source Evidence Incomplete" in controls
    assert "analytics_materialization.source_warning" in controls
    assert "Forecast Snapshot Available · Source Evidence Incomplete" not in page


def test_forecast_overview_uses_operational_posture_and_methodology_boundary() -> None:
    overview = read("app/templates/analytics/forecast/partials/_overview_methodology.html")

    for label in (
        "Projected Capacity Posture",
        "Warning Resources",
        "Critical Resources",
        "Nearest Critical",
        "Methodology Boundary",
        "Observation History",
        "Projection Model",
        "Forecast Horizon",
    ):
        assert label in overview

    assert "xl:col-span-2" in overview
    assert "divide-y divide-outline-subtle" in overview
    assert "<details" not in overview


def test_shared_analytics_tabs_accept_embedded_mode_and_safe_x_data_json() -> None:
    workspace = read("app/templates/analytics/components/_analysis_workspace.html")
    tabs = read("app/templates/analytics/components/_content_tabs.html")

    assert "data-analytics-tabset" in workspace
    assert "data-default-tab" in workspace
    assert "x-data='kaoriAnalyticsTabs(" in workspace
    assert "initial_tab|tojson" in workspace
    assert "allowed_tabs|tojson" in workspace
    assert "{% macro render(tabset_id, tabs, aria_label, embedded=false) %}" in tabs
    assert "if embedded else" in tabs


def test_forecast_panels_have_native_hidden_fallback_and_post_swap_hydration() -> None:
    section = read("app/templates/analytics/forecast/partials/_forecast_section.html")
    controls_js = read("app/static/js/analytics_controls.js")

    assert "data-analytics-tab-panel=\"{{ resource_key }}\"" in section
    assert "data-analytics-tab-panel=\"trend\"" in section
    assert "data-analytics-tab-panel=\"recommendations\"" in section
    assert "x-bind:hidden=\"activeTab !== '{{ resource_key }}'\"" in section
    assert "hidden\n             x-cloak" in section
    assert "function stabilizeAnalyticsTabsets(root)" in controls_js
    assert "window.Alpine.initTree(tabset)" in controls_js
    assert "panel.hidden = panel.dataset.analyticsTabPanel !== activeTab" in controls_js
    assert "stabilizeAnalyticsTabsets(root)" in controls_js
