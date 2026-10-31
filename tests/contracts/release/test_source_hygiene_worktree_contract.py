"""Source Hygiene distinguishes linked Git worktrees from unpacked release archives."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_HYGIENE = ROOT / 'scripts/verify_source_hygiene.sh'


def _fixture_source(directory: Path) -> None:
    scripts = directory / 'scripts'
    scripts.mkdir(parents=True)
    shutil.copyfile(SOURCE_HYGIENE, scripts / 'verify_source_hygiene.sh')
    (directory / '.gitignore').write_text('.ruff_cache/\ntmp/\n', encoding='utf-8')
    (directory / '.dockerignore').write_text('.ruff_cache/\ntmp/\n', encoding='utf-8')


def _generated_files(directory: Path) -> None:
    ruff_cache = directory / '.ruff_cache' / '0.17.3' / 'sample'
    ruff_cache.parent.mkdir(parents=True)
    ruff_cache.write_text('cache\n', encoding='utf-8')
    diagnostic = directory / 'tmp' / 'ci-artifacts' / 'static-output' / 'verification-report.md'
    diagnostic.parent.mkdir(parents=True)
    diagnostic.write_text('runtime evidence\n', encoding='utf-8')


def _run_hygiene(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['bash', 'scripts/verify_source_hygiene.sh'],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )


def _git(directory: Path, *arguments: str) -> None:
    subprocess.run(['git', *arguments], cwd=directory, capture_output=True, text=True, check=True)


def test_normal_and_linked_worktrees_ignore_untracked_generated_artifacts(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    _fixture_source(checkout)
    _git(checkout, 'init', '-q')
    _git(checkout, 'add', '.gitignore', '.dockerignore', 'scripts/verify_source_hygiene.sh')
    _git(
        checkout,
        '-c',
        'user.name=KAORI CI Test',
        '-c',
        'user.email=ci-test@example.invalid',
        'commit',
        '-qm',
        'Source hygiene fixture',
    )
    linked = tmp_path / 'linked-worktree'
    _git(checkout, 'worktree', 'add', '--detach', str(linked))
    assert (checkout / '.git').is_dir()
    assert (linked / '.git').is_file()

    for workspace in (checkout, linked):
        _generated_files(workspace)
        check = _run_hygiene(workspace)
        assert check.returncode == 0, check.stderr
        assert '[KAORI hygiene] tracked source is clean (3 files checked).' in check.stdout


def test_source_archive_rejects_generated_cache_and_diagnostics(tmp_path: Path) -> None:
    archive = tmp_path / 'unpacked-source-archive'
    _fixture_source(archive)
    _generated_files(archive)

    check = _run_hygiene(archive)
    assert check.returncode != 0
    assert 'generated/runtime artifacts are present in source archive' in check.stderr
    assert '.ruff_cache/0.17.3/sample' in check.stderr
    assert 'tmp/ci-artifacts/static-output/verification-report.md' in check.stderr


def test_tracked_generated_file_still_fails_hygiene(tmp_path: Path) -> None:
    checkout = tmp_path / 'checkout'
    _fixture_source(checkout)
    _git(checkout, 'init', '-q')
    _generated_files(checkout)
    _git(checkout, 'add', '.gitignore', '.dockerignore', 'scripts/verify_source_hygiene.sh')
    _git(checkout, 'add', '-f', '.ruff_cache/0.17.3/sample')

    check = _run_hygiene(checkout)
    assert check.returncode != 0
    assert 'generated/runtime artifacts are present in tracked source' in check.stderr
    assert '.ruff_cache/0.17.3/sample' in check.stderr
