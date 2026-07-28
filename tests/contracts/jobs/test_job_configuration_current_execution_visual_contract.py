from pathlib import Path

TEMPLATE = Path("app/templates/jobs/configuration/_execution_activity.html")


def test_current_execution_uses_visual_status_workspace():
    source = TEMPLATE.read_text(encoding="utf-8")
    assert "Current Execution" in source
    assert "bg-kaori-soft/40" in source
    assert "Execution Progress" in source
    assert "Ready For Execution" in source


def test_current_execution_keeps_single_determinate_progress_bar():
    source = TEMPLATE.read_text(encoding="utf-8")
    current_block = source.split("Current Execution", 1)[1].split("Manual runs use", 1)[0]
    assert current_block.count("progress_bar.determinate") == 1
    assert "animate-pulse" not in current_block


def test_current_execution_metadata_remains_compact():
    source = TEMPLATE.read_text(encoding="utf-8")
    for label in ("Scope", "Queue", "Requested By", "Started"):
        assert label in source
    assert "lg:grid-cols-4" in source
