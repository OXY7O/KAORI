from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app" / "templates"


def _read(relative: str) -> str:
    return (TEMPLATES / relative).read_text(encoding="utf-8")


def test_alerts_and_anomalies_are_primary_workspace_tabs() -> None:
    template = _read("analytics/alerts/index.html")

    assert "('alerts', 'Alerts', 'bell-ring')" in template
    assert "('anomalies', 'Anomalies', 'radar')" in template
    assert "activeSignalTab" not in template
    assert "Alert Detail Type" not in template
    assert "alerts-content-panel-alerts" in template
    assert "alerts-content-panel-anomalies" in template


def test_record_tables_do_not_force_horizontal_scrolling() -> None:
    alerts = _read("analytics/alerts/partials/_alerts_table.html")
    anomalies = _read("analytics/alerts/partials/_anomalies_table.html")
    combined = alerts + anomalies

    assert "overflow-x-auto" not in combined
    assert "min-w-[" not in combined
    assert "<table" not in combined
    assert "grid-cols-12" in alerts
    assert "grid-cols-12" in anomalies


def test_record_actions_have_dedicated_responsive_space() -> None:
    alerts = _read("analytics/alerts/partials/_alerts_table_row.html")
    anomalies = _read("analytics/alerts/partials/_anomalies_table_row.html")

    for content in (alerts, anomalies):
        assert "lg:col-span-2 lg:justify-end" in content
        assert "w-full shrink-0 lg:w-auto" in content
        assert "View More" in content
        assert "aria-controls" in content


def test_expanded_record_content_uses_one_workspace_with_internal_dividers() -> None:
    alerts = _read("analytics/alerts/partials/_alerts_table_row.html")
    anomalies = _read("analytics/alerts/partials/_anomalies_table_row.html")

    assert "Operational Context" in alerts
    assert "Recommended Investigation Path" in alerts
    assert "Labels" in alerts
    assert "Annotations" in alerts
    assert "Anomaly Context" in anomalies
    assert "Recommended Anomaly Review" in anomalies
    assert "Next Operational Action" in anomalies

    for content in (alerts, anomalies):
        assert "grid lg:grid-cols-3" in content
        assert "lg:border-l lg:border-t-0" in content
        assert "overflow-x-auto" not in content
        assert "truncate" not in content
