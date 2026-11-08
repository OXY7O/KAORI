"""Regression for publication inventory invoked from a nested directory (#4212)."""

import subprocess
from pathlib import Path

from scripts.publication_inventory import inventory


def test_nested_directory_inventory_counts_full_repository(tmp_path: Path):
    repo = tmp_path / 'sample'
    repo.mkdir()

    def git(*args):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)

    git('init', '-q')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    (repo / 'root.txt').write_text('root')
    nested = repo / 'nested'
    nested.mkdir()
    (nested / 'child.txt').write_text('child')
    git('add', '.')
    git('commit', '-qm', 'fixture')

    root_result = inventory(repo)
    nested_result = inventory(nested)
    assert root_result == nested_result
    assert nested_result['tracked_head_file_count'] == 2
    assert nested_result['assessment'] == 'INCOMPLETE'
