#!/usr/bin/env python3
"""Remove retired test namespaces after the domain-first test migration.

The cleanup fails closed if a source file does not already exist at its canonical
replacement path. This prevents accidental deletion of local tests that were
created after the migration patch was produced.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAPPINGS: tuple[tuple[str, str], ...] = (
    ('tests/analytics/object_storage', 'tests/storage/object_storage/analytics'),
    ('tests/analytics', 'tests/kubernetes/analytics'),
    ('tests/dashboards', 'tests/kubernetes/dashboard'),
    ('tests/governance', 'tests/kubernetes/governance'),
    ('tests/inventory/kubernetes', 'tests/kubernetes/inventory'),
    ('tests/inventory/object_storage', 'tests/storage/object_storage/inventory'),
    ('tests/jobs', 'tests/platform_operations/jobs'),
    ('tests/kubernetes_operations', 'tests/kubernetes/operations'),
    ('tests/unit/auth', 'tests/unit/access/authentication'),
    ('tests/unit/analytics', 'tests/unit/kubernetes/analytics'),
    ('tests/unit/dashboards', 'tests/unit/kubernetes/dashboard'),
    ('tests/unit/governance', 'tests/unit/kubernetes/governance'),
    ('tests/unit/inventory/kubernetes', 'tests/unit/kubernetes/inventory'),
    ('tests/unit/kubernetes_operations', 'tests/unit/kubernetes/operations'),
    ('tests/integration/analytics', 'tests/integration/kubernetes/analytics'),
    ('tests/integration/dashboards', 'tests/integration/kubernetes/dashboard'),
    ('tests/integration/governance', 'tests/integration/kubernetes/governance'),
    ('tests/integration/inventory/kubernetes', 'tests/integration/kubernetes/inventory'),
    ('tests/integration/kubernetes_operations', 'tests/integration/kubernetes/operations'),
    ('tests/security/auth', 'tests/security/access/authentication'),
    ('tests/security/analytics', 'tests/security/kubernetes/analytics'),
    ('tests/security/dashboards', 'tests/security/kubernetes/dashboard'),
    ('tests/security/governance', 'tests/security/kubernetes/governance'),
    ('tests/security/inventory', 'tests/security/kubernetes/inventory'),
    ('tests/security/kubernetes_operations', 'tests/security/kubernetes/operations'),
    ('tests/rendering/auth', 'tests/rendering/access/authentication'),
    ('tests/rendering/analytics', 'tests/rendering/kubernetes/analytics'),
    ('tests/rendering/dashboards', 'tests/rendering/kubernetes/dashboard'),
    ('tests/rendering/governance', 'tests/rendering/kubernetes/governance'),
    ('tests/rendering/inventory', 'tests/rendering/kubernetes/inventory'),
    ('tests/rendering/kubernetes_operations', 'tests/rendering/kubernetes/operations'),
    ('tests/e2e/auth', 'tests/e2e/access/authentication'),
    ('tests/e2e/analytics', 'tests/e2e/kubernetes/analytics'),
    ('tests/e2e/dashboards', 'tests/e2e/kubernetes/dashboard'),
    ('tests/e2e/governance', 'tests/e2e/kubernetes/governance'),
    ('tests/e2e/inventory/kubernetes', 'tests/e2e/kubernetes/inventory'),
    ('tests/e2e/kubernetes_operations', 'tests/e2e/kubernetes/operations'),
    ('tests/debug/inventory/object_storage', 'tests/debug/storage/object_storage/inventory'),
    ('tests/contracts/auth', 'tests/contracts/access/authentication'),
    ('tests/contracts/governance', 'tests/contracts/kubernetes/governance'),
    ('tests/contracts/kubernetes_operations', 'tests/contracts/kubernetes/operations'),
    ('tests/contracts/inventory/object_storage', 'tests/contracts/storage/object_storage/inventory'),
    ('tests/contracts/jobs', 'tests/contracts/platform_operations/jobs'),
    ('tests/contracts/notifications', 'tests/contracts/platform_operations/notifications'),
)

IGNORED_NAMES = {'__pycache__', '.pytest_cache'}
IGNORED_SUFFIXES = {'.pyc', '.pyo'}


def _source_files(path: Path) -> list[Path]:
    return [
        item
        for item in path.rglob('*')
        if item.is_file()
        and not any(part in IGNORED_NAMES for part in item.parts)
        and item.suffix not in IGNORED_SUFFIXES
    ]


def _validate_mapping(source: Path, destination: Path) -> list[str]:
    missing: list[str] = []
    for item in _source_files(source):
        relative = item.relative_to(source)
        if not (destination / relative).is_file():
            missing.append(relative.as_posix())
    return missing


def main() -> int:
    for source_raw, destination_raw in MAPPINGS:
        source = ROOT / source_raw
        if not source.exists():
            continue
        destination = ROOT / destination_raw
        if not destination.exists():
            print('FAIL — retired test namespace cleanup')
            print(f'- {source_raw}: canonical destination is missing: {destination_raw}')
            return 1
        missing = _validate_mapping(source, destination)
        if missing:
            print('FAIL — retired test namespace cleanup')
            print(f'- {source_raw}: files are not represented at {destination_raw}: {", ".join(missing)}')
            return 1
        shutil.rmtree(source)
        print(f'Removed {source.relative_to(ROOT)}')

    # Remove empty legacy parent shells left after more-specific moves.
    for relative in (
        'tests/inventory',
        'tests/unit/inventory',
        'tests/integration/inventory',
        'tests/e2e/inventory',
        'tests/debug/inventory',
        'tests/contracts/inventory',
    ):
        path = ROOT / relative
        if path.exists() and not any(path.iterdir()):
            path.rmdir()

    print('PASS — retired test namespaces removed safely')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
