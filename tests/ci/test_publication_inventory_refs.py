"""Regression coverage for metadata-only publication inventory (#4212)."""

import importlib.util
import subprocess
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / 'scripts' / 'publication_inventory.py'
spec = importlib.util.spec_from_file_location('publication_inventory', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)


def test_full_checkout_counts_remote_and_other_refs_without_names(tmp_path):
    repo = tmp_path / 'sample'
    repo.mkdir()
    run(repo, 'init')
    run(
        repo,
        '-c',
        'user.name=Tester',
        '-c',
        'user.email=test@example.invalid',
        'commit',
        '--allow-empty',
        '-m',
        'initial',
    )
    run(repo, 'update-ref', 'refs/remotes/origin/private-topic', 'HEAD')
    run(repo, 'update-ref', 'refs/notes/audit', 'HEAD')
    result = module.inventory(repo)
    assert result['shallow_checkout'] is False
    assert result['remote_tracking_ref_count'] == 1
    assert result['other_local_ref_count'] == 1
    assert result['assessment'] == 'INCOMPLETE'
    assert 'private-topic' not in str(result)


def test_shallow_checkout_is_reported_without_claiming_clearance(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    run(source, 'init')
    for i in range(2):
        run(
            source,
            '-c',
            'user.name=Tester',
            '-c',
            'user.email=test@example.invalid',
            'commit',
            '--allow-empty',
            '-m',
            f'commit-{i}',
        )
    clone = tmp_path / 'shallow'
    subprocess.run(['git', 'clone', '--quiet', '--depth', '1', source.as_uri(), str(clone)], check=True)
    result = module.inventory(clone)
    assert result['shallow_checkout'] is True
    assert result['history_commit_count'] == 1
    assert result['assessment'] == 'INCOMPLETE'
