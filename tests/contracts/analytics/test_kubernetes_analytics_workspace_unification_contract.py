from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates" / "analytics"


def read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_alert_signal_state_uses_separate_semantic_columns() -> None:
    table = read("alerts/partials/_alerts_table.html")
    content = read("alerts/partials/_alerts_table_row.html")
    main_row = content.split('<div id="{{ row_key }}-details"', 1)[0]
    assert ">Severity</div>" in table
    assert ">State</div>" in table
    assert "table_label.status_label(alert.severity|title" in main_row
    assert "table_label.status_label(alert.status|title" in main_row


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


def test_forecast_resource_tabs_and_shared_interactive_legends() -> None:
    content = read("forecast/partials/_forecast_section.html")
    for label in ("CPU Forecast", "Memory Forecast", "Storage Forecast", "Pod Forecast"):
        assert label in content
    assert "Historical" in content
    assert "Projection" in content
    assert "Warning" in content
    assert "Critical" in content
    js = (ROOT / "app" / "static" / "js" / "analytics_forecast_chart.js").read_text(encoding="utf-8")
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
