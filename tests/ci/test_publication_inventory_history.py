"""Regression for publication history inventory (#4212)."""
import importlib.util
import subprocess
from pathlib import Path


def test_reachable_history_count_from_subdirectory(tmp_path):
    repo = tmp_path / "sample"
    nested = repo / "nested"
    nested.mkdir(parents=True)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])
    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Inventory Test")
    (nested / "first.txt").write_text("initial")
    git("add", ".")
    git("commit", "-qm", "initial")
    (nested / "first.txt").unlink()
    (nested / "second.txt").write_text("next")
    git("add", "-A")
    git("commit", "-qm", "second")

    source = Path(__file__).resolve().parents[2] / "scripts" / "publication_inventory.py"
    spec = importlib.util.spec_from_file_location("publication_inventory", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.inventory(nested)
    expected = len(git("rev-list", "--objects", "--no-object-names", "--all").splitlines())
    assert result["reachable_history_object_count"] == expected
    assert expected > 0
    assert result["tracked_head_file_count"] == 1
    assert result["assessment"] == "INCOMPLETE"
