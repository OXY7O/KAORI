from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates" / "analytics"


def read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_alert_signal_state_is_single_row() -> None:
    content = read("alerts/partials/_alerts_table_row.html")
    assert 'flex min-w-0 flex-wrap items-center gap-2' in content
    assert "alert.severity|title" in content
    assert "alert.status|title" in content


def test_all_target_pages_use_unified_controls_and_readiness() -> None:
    for relative in (
        "forecast/partials/_controls_readiness.html",
        "workload/partials/_controls_readiness.html",
        "storage/partials/_controls_readiness.html",
        "capacity/partials/_controls_readiness.html",
        "utilization/partials/_readiness_scope.html",
    ):
        content = read(relative)
        assert "controls_readiness" in content
        assert "prometheus_status" in content
        assert "analytics_materialization" in content


def test_overviews_are_outside_tab_workspaces() -> None:
    pages = {
        "forecast/index.html": "_overview_methodology.html",
        "workload/index.html": "_overview.html",
        "storage/index.html": "_overview.html",
        "capacity/index.html": "_overview.html",
        "utilization/index.html": "_overview.html",
    }
    for relative, overview in pages.items():
        content = read(relative)
        assert overview in content
        assert content.index(overview) < content.index("tabbed(") if "tabbed(" in content else True


def test_tabs_are_embedded_in_workspace_boxes() -> None:
    for relative in (
        "forecast/partials/_forecast_section.html",
        "workload/index.html",
        "storage/partials/_storage_section.html",
        "capacity/index.html",
        "utilization/index.html",
    ):
        content = read(relative)
        assert "analytics_workspace.tabbed" in content or "embedded=true" in content


def test_forecast_resource_tabs_and_custom_legends() -> None:
    content = read("forecast/partials/_forecast_section.html")
    for label in ("CPU Forecast", "Memory Forecast", "Storage Forecast", "Pod Forecast"):
        assert label in content
    assert "Historical" in content
    assert "Forecast" in content
    assert "Warning" in content
    assert "Critical" in content
    js = (ROOT / "app" / "static" / "js" / "analytics_forecast.js").read_text(encoding="utf-8")
    assert "display: false" in js


def test_recommendations_are_non_expandable_operational_rows() -> None:
    for relative in (
        "forecast/partials/_forecast_section.html",
        "workload/partials/_recommendations.html",
        "storage/partials/_recommendations.html",
        "capacity/partials/_recommendations.html",
        "utilization/partials/_recommendations.html",
    ):
        content = read(relative)
        assert "<details" not in content
        assert "<summary" not in content
        assert "divide-y divide-outline-subtle" in content
