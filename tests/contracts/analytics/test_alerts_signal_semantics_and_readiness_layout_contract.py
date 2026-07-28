from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / "app" / "templates" / "analytics" / "alerts" / "partials"


def _read(name: str) -> str:
    return (PARTIALS / name).read_text(encoding="utf-8")


def test_active_alert_severity_and_state_have_explicit_columns() -> None:
    table = _read("_alerts_table.html")
    row = _read("_alerts_table_row.html")
    main_row = row.split('<div id="{{ row_key }}-details"', 1)[0]

    assert "Severity &amp; State" not in table
    assert ">Severity</div>" in table
    assert ">State</div>" in table
    assert "table_label.status_label(alert.severity|title" in main_row
    assert "table_label.status_label(alert.status|title" in main_row


def test_recommendation_badges_explain_priority_and_origin() -> None:
    recommendations = _read("_recommendations.html")

    assert "recommendation.priority" in recommendations
    assert "recommendation.source_label" in recommendations
    assert "recommendation.href" in recommendations


def test_escalation_readiness_does_not_force_full_width_child() -> None:
    readiness = _read("_incident_readiness.html")

    assert "min-w-full" not in readiness
    assert "xl:grid-cols-4" in readiness
    assert "lg:grid-cols-2" in readiness
    assert "Readiness Checks" in readiness
    assert "Score {{ incident_readiness.score }}/100" in readiness
