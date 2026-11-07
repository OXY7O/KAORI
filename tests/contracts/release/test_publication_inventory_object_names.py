"""Regression: Git object counts must not depend on newline-bearing filenames (#4212)."""
import importlib.util
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "publication_inventory.py"


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    ).stdout


def test_history_object_count_ignores_filename_newlines(tmp_path):
    spec = importlib.util.spec_from_file_location("publication_inventory", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "audit@example.invalid")
    _git(tmp_path, "config", "user.name", "Audit Test")
    (tmp_path / "normal.txt").write_text("first\n")
    (tmp_path / "line\nbreak.txt").write_text("second\n")
    _git(tmp_path, "add", "--all")
    _git(tmp_path, "commit", "-qm", "test history")

    expected = len(_git(tmp_path, "rev-list", "--objects", "--no-object-names", "--all").splitlines())
    result = module.inventory(tmp_path)
    assert result["reachable_history_object_count"] == expected
    assert result["assessment"] == "INCOMPLETE"
    assert "line\nbreak.txt" not in str(result)
