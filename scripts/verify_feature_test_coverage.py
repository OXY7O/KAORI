#!/usr/bin/env python3
"""Require functional characterization evidence for Inventory and Analytics foundations."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

_REQUIRED_TEST_FILES = {
    'tests/analytics/test_alerts_characterization.py': 5,
    'tests/analytics/test_capacity_logic_characterization.py': 2,
    'tests/analytics/test_forecast_logic_characterization.py': 3,
    'tests/analytics/test_storage_logic_characterization.py': 3,
    'tests/analytics/test_top_consumers_logic_characterization.py': 4,
    'tests/analytics/test_utilization_logic_characterization.py': 3,
    'tests/analytics/test_workload_logic_characterization.py': 3,
    'tests/inventory/test_inventory_presentation_characterization.py': 2,
    'tests/inventory/test_topology_logic_characterization.py': 2,
    'tests/kubernetes/test_fleet_inventory_snapshot.py': 2,
    'tests/kubernetes/test_inventory_current_generation_filter.py': 1,
    'tests/kubernetes/test_inventory_generation_consistency.py': 1,
    'tests/kubernetes/test_inventory_persistence_atomicity.py': 2,
    'tests/kubernetes/test_inventory_sync_canonical_resolution.py': 2,
}


def _test_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith('test_')
    ]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, minimum_tests in _REQUIRED_TEST_FILES.items():
        path = root / relative_path
        if not path.exists():
            errors.append(f'{relative_path}: required functional characterization file is missing')
            continue
        try:
            tests = _test_functions(path)
        except SyntaxError as exc:
            errors.append(f'{relative_path}:{exc.lineno}: invalid Python test module')
            continue
        if len(tests) < minimum_tests:
            errors.append(
                f'{relative_path}: {len(tests)} behavior tests found; '
                f'at least {minimum_tests} are required'
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate Inventory and Analytics functional characterization coverage.'
    )
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()

    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI feature characterization coverage is present across '
        f'{len(_REQUIRED_TEST_FILES)} required test modules.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
