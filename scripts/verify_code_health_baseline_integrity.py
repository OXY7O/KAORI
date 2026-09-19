#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path('app')
BASELINE_PATH = ROOT / 'docs/architecture/code-health-debt-baseline.json'
VERIFIER_PATH = ROOT / 'scripts/verify_code_health.py'
EXPECTED_DEFAULTS = {
    'module_lines': 800,
    'function_lines': 160,
    'branch_points': 30,
    'arguments': 8,
}


def _load_code_health_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location('kaori_verify_code_health', VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError('Could not load the canonical code-health verifier.')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    import os

    os.chdir(ROOT)
    try:
        verifier = _load_code_health_module()
        expected = verifier.build_baseline(APP_ROOT)
        actual = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}')
        return 1

    errors: list[str] = []
    if actual.get('defaults') != EXPECTED_DEFAULTS:
        errors.append(
            'code-health default ceilings must remain 800 module lines, 160 function lines, '
            '30 branch points, and 8 arguments'
        )

    for key in (
        'module_line_limits',
        'function_line_limits',
        'function_branch_limits',
        'function_argument_limits',
        'broad_exception_limit',
    ):
        if actual.get(key) != expected.get(key):
            errors.append(
                f'{key} is not an exact snapshot of the current bounded debt; '
                'run `python scripts/verify_code_health.py --write-baseline` only after reviewing the code change'
            )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI code-health baseline integrity passed: default ceilings are unchanged and '
        'the debt ledger exactly matches the current release-candidate source without slack.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
