#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from pathlib import Path

_REQUIRED_MARKERS = {'functional', 'integration', 'contract', 'migration', 'debug'}
_DIAGNOSTIC_TOKENS = {'debug', 'diagnostic', 'reproduction', 'repro'}


def _configured_markers(pytest_ini: Path) -> set[str]:
    markers: set[str] = set()
    in_markers = False
    for raw_line in pytest_ini.read_text(encoding='utf-8').splitlines():
        line = raw_line.rstrip()
        if line.strip() == 'markers =':
            in_markers = True
            continue
        if in_markers:
            if not line.startswith((' ', '\t')):
                break
            marker = line.strip().split(':', 1)[0].strip()
            if marker:
                markers.add(marker)
    return markers


def _has_collection_hook(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except SyntaxError:
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'pytest_collection_modifyitems'
        for node in tree.body
    )


def validate(root: Path) -> list[str]:
    tests_root = root / 'tests'
    errors: list[str] = []

    configured = _configured_markers(root / 'pytest.ini')
    missing_markers = sorted(_REQUIRED_MARKERS - configured)
    if missing_markers:
        errors.append(f'pytest.ini is missing markers: {missing_markers}')

    canonical_conftest = tests_root / 'conftest.py'
    if not canonical_conftest.exists() or not _has_collection_hook(canonical_conftest):
        errors.append('tests/conftest.py must own the canonical path-based marker hook')

    for path in sorted(tests_root.rglob('conftest.py')):
        if path == canonical_conftest:
            continue
        if _has_collection_hook(path):
            errors.append(f'{path.relative_to(root)} duplicates the canonical test taxonomy hook')

    for path in sorted(tests_root.rglob('test_*.py')):
        relative = path.relative_to(tests_root)
        if len(relative.parts) == 1:
            errors.append(f'{path.relative_to(root)} must live in a purpose/domain folder')
            continue

        source = path.read_text(encoding='utf-8')
        bucket = relative.parts[0]
        lowered_name = path.stem.lower()
        looks_diagnostic = any(token in lowered_name for token in _DIAGNOSTIC_TOKENS)
        has_debug_marker = 'pytest.mark.debug' in source

        if bucket != 'debug' and (looks_diagnostic or has_debug_marker):
            errors.append(f'{path.relative_to(root)} is diagnostic and must live under tests/debug/')
        if bucket == 'debug' and 'pytest.mark.functional' in source:
            errors.append(f'{path.relative_to(root)} may not be marked as release functional evidence')

    quality_gate = (root / 'scripts' / 'quality_gate.sh').read_text(encoding='utf-8')
    if "-m 'not debug'" not in quality_gate and '-m "not debug"' not in quality_gate:
        errors.append('quality_gate.sh must exclude debug tests from the release test run')

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate KAORI test purpose and location taxonomy.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()

    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    test_files = len(list((args.root / 'tests').rglob('test_*.py')))
    print(f'KAORI test taxonomy is valid across {test_files} test modules.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
