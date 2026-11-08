"""Regression coverage for metadata inventory on an initialized, empty Git repository."""

import importlib.util
import subprocess
from pathlib import Path


def test_unborn_head_inventory_is_incomplete(tmp_path):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        'publication_inventory', root / 'scripts' / 'publication_inventory.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    repo = tmp_path / 'empty'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    result = module.inventory(repo)

    assert result['assessment'] == 'INCOMPLETE'
    assert result['head_commit_present'] is False
    assert result['head_outside_local_refs'] is False
    assert result['history_commit_count'] == 0
    assert result['reachable_history_object_count'] == 0
    assert result['tracked_head_file_count'] == 0
