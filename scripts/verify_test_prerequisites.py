#!/usr/bin/env python3
"""Verify KAORI release-test collection prerequisites before running pytest."""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / 'tests'
REQUIRED_TEST_PACKAGES = {
    'pypdf': '6.14.2',
    'pytest': None,
}


def _dependency_errors() -> list[str]:
    errors: list[str] = []
    for name, expected_version in REQUIRED_TEST_PACKAGES.items():
        if importlib.util.find_spec(name) is None:
            errors.append(f'missing development test dependency: {name}')
            continue
        if expected_version is None:
            continue
        installed_version = metadata.version(name)
        if installed_version != expected_version:
            errors.append(
                f'development test dependency {name} is {installed_version}; expected locked version {expected_version}'
            )
    return errors


def _duplicate_test_basenames() -> dict[str, list[str]]:
    matches: dict[str, list[str]] = defaultdict(list)
    for path in sorted(TEST_ROOT.rglob('test_*.py')):
        matches[path.name].append(str(path.relative_to(ROOT)))
    return {name: paths for name, paths in matches.items() if len(paths) > 1}


def main() -> int:
    errors: list[str] = []

    dependency_errors = _dependency_errors()
    if dependency_errors:
        errors.extend(
            f'{error}; install requirements/dev.txt or rebuild the Dev Container' for error in dependency_errors
        )

    duplicates = _duplicate_test_basenames()
    for basename, paths in sorted(duplicates.items()):
        errors.append(f'duplicate pytest module basename {basename}: {", ".join(paths)}')

    if errors:
        print('FAIL — KAORI Test Prerequisites')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Test Prerequisites')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
