from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / "app" / "templates" / "analytics" / "alerts" / "partials"


def _read(name: str) -> str:
    return (PARTIALS / name).read_text(encoding="utf-8")


def test_active_alert_signal_state_has_explicit_meaning() -> None:
    table = _read("_alerts_table.html")
    row = _read("_alerts_table_row.html")

    assert "Severity &amp; State" in table
    assert ">Severity</p>" not in row
    assert ">Alert State</p>" not in row
    assert "space-y-1 lg:col-span-2" in row
    assert "Severity: " in row
    assert "State: " in row


def test_recommendation_badges_explain_priority_and_origin() -> None:
    recommendations = _read("_recommendations.html")

    assert "Priority: " in recommendations
    assert "Derived From: " in recommendations
    assert "icon='database'" in recommendations


def test_escalation_readiness_does_not_force_full_width_child() -> None:
    readiness = _read("_incident_readiness.html")

    assert "min-w-full" not in readiness
    assert "xl:grid-cols-2" in readiness
    assert "Overall Score:" in readiness
    assert "Readiness Checks" in readiness
    assert "xl:grid-cols-4" in readiness
