#!/usr/bin/env python3
"""Verify KAORI release-test collection prerequisites before running pytest."""

from __future__ import annotations

import importlib.util
import re
from collections import defaultdict
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / 'tests'
FUNCTIONAL_TEST_BUCKETS = (
    'welcome',
    'dashboards',
    'analytics',
    'inventory',
    'governance',
    'kubernetes_operations',
)
_DIRECT_MODULE_ASSIGNMENT = re.compile(r'^\s*sys\.modules\[[^\]]+\]\s*=', re.MULTILINE)

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



def _unsafe_module_registry_mutations() -> dict[str, list[str]]:
    unsafe: dict[str, list[str]] = {}
    for bucket in FUNCTIONAL_TEST_BUCKETS:
        root = TEST_ROOT / bucket
        if not root.exists():
            continue
        for path in sorted(root.rglob('test_*.py')):
            source = path.read_text(encoding='utf-8')
            direct_lines = [
                line.strip()
                for line in source.splitlines()
                if 'sys.modules.setdefault' in line or _DIRECT_MODULE_ASSIGNMENT.match(line)
            ]
            if not direct_lines:
                continue
            has_explicit_restore = 'finally:' in source and any(
                marker in source for marker in ('previous', 'original', 'saved_modules')
            )
            if has_explicit_restore:
                continue
            unsafe[str(path.relative_to(ROOT))] = direct_lines
    return unsafe


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

    unsafe_modules = _unsafe_module_registry_mutations()
    for relative, mutations in sorted(unsafe_modules.items()):
        errors.append(
            'functional test mutates sys.modules without restore-safe isolation: '
            f'{relative} ({len(mutations)} direct mutation(s)); use monkeypatch.setitem or explicit try/finally restore'
        )

    if errors:
        print('FAIL — KAORI Test Prerequisites')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Test Prerequisites')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
