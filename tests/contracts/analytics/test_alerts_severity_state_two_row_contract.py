from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROW = (
    ROOT
    / "app"
    / "templates"
    / "analytics"
    / "alerts"
    / "partials"
    / "_alerts_table_row.html"
)


def test_severity_and_alert_state_use_two_visual_rows() -> None:
    row = ROW.read_text(encoding="utf-8")

    assert 'class="grid grid-cols-2 gap-2"' in row
    assert 'class="mt-1 grid grid-cols-2 items-start gap-2"' in row
    assert row.count(">Severity</p>") == 1
    assert row.count(">Alert State</p>") == 1


def test_severity_and_state_badges_keep_independent_semantics() -> None:
    row = ROW.read_text(encoding="utf-8")

    assert "alert.severity|title" in row
    assert "tone=severity_tone" in row
    assert "alert.status|title" in row
    assert "tone=status_tone" in row
