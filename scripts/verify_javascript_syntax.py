from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = (
    ROOT / 'app' / 'static' / 'js',
    ROOT / 'frontend',
    ROOT / 'scripts',
)


def _javascript_files() -> list[Path]:
    files: set[Path] = set()
    for search_root in SEARCH_ROOTS:
        if not search_root.exists():
            continue
        files.update(search_root.rglob('*.js'))
        files.update(search_root.rglob('*.mjs'))
    return sorted(files)


def verify() -> None:
    node = shutil.which('node')
    if not node:
        raise AssertionError('Node.js is required for KAORI first-party JavaScript syntax verification.')

    files = _javascript_files()
    if not files:
        raise AssertionError('No first-party JavaScript files were discovered for syntax verification.')

    failures: list[str] = []
    for path in files:
        result = subprocess.run(
            [node, '--check', str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            relative = path.relative_to(ROOT)
            detail = (result.stderr or result.stdout).strip()
            failures.append(f'{relative}: {detail}')

    if failures:
        raise AssertionError('JavaScript syntax verification failed:\n' + '\n'.join(failures))

    print(f'KAORI first-party JavaScript syntax passed across {len(files)} files.')


if __name__ == '__main__':
    verify()
