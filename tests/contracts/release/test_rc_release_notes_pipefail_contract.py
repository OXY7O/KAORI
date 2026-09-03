from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-staging-image.yml"


def test_rc_release_notes_do_not_use_head_pipeline_under_pipefail() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "git log --format='- %s (%h)' \"$change_range\" | head -n 30" not in workflow
    assert "git log -n 30 --format='- %s (%h)' \"$change_range\"" in workflow
