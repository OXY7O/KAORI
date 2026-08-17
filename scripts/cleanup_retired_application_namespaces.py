from __future__ import annotations

import shutil
from pathlib import Path

from verify_application_package_architecture import FORBIDDEN_ROOTS, ROOT

APP = ROOT / 'app'
IGNORABLE_FILE_NAMES = {'.DS_Store'}


def _meaningful_entries(path: Path) -> list[Path]:
    entries: list[Path] = []
    for candidate in path.rglob('*'):
        if candidate.is_dir():
            continue
        if '__pycache__' in candidate.parts or candidate.suffix in {'.pyc', '.pyo'}:
            continue
        if candidate.name in IGNORABLE_FILE_NAMES:
            continue
        entries.append(candidate)
    return entries


def main() -> int:
    blocked: list[str] = []
    removed: list[str] = []

    for name in sorted(FORBIDDEN_ROOTS):
        path = APP / name
        if not path.exists():
            continue
        meaningful = _meaningful_entries(path)
        if meaningful:
            blocked.append(
                f'app/{name} still contains source/artifact files: '
                + ', '.join(item.relative_to(ROOT).as_posix() for item in meaningful[:5])
            )
            continue
        shutil.rmtree(path)
        removed.append(f'app/{name}')

    if blocked:
        print('FAIL — KAORI Retired Namespace Cleanup')
        for error in blocked:
            print(f'- {error}')
        return 1

    if removed:
        print('Removed retired empty/cache-only namespaces:')
        for path in removed:
            print(f'- {path}')
    else:
        print('No retired application namespaces require cleanup.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
