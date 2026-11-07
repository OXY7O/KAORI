"""Gitlink/submodule publication inventory regression (#4212)."""
import importlib.util
import subprocess
from pathlib import Path


def test_gitlink_is_counted_without_exposing_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])
    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Inventory Test")
    (repo / "README.md").write_text("safe")
    git("add", "README.md")
    git("commit", "-qm", "initial")
    head = git("rev-parse", "HEAD").decode().strip()
    git("update-index", "--add", "--cacheinfo", f"160000,{head},vendor-private")
    git("commit", "-qm", "add gitlink")

    source = Path(__file__).resolve().parents[2] / "scripts" / "publication_inventory.py"
    spec = importlib.util.spec_from_file_location("publication_inventory", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.inventory(repo)
    assert result["tracked_gitlink_count"] == 1
    assert result["tracked_head_file_count"] == 2
    assert result["assessment"] == "INCOMPLETE"
    assert "vendor-private" not in str(result)
