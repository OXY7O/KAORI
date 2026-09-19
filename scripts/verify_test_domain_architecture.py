#!/usr/bin/env python3
"""Verify that KAORI test paths mirror the domain-first application architecture."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / 'tests'

PURPOSE_BUCKETS = ('unit', 'integration', 'security', 'rendering', 'e2e')
RETIRED_PURPOSE_CHILDREN = {
    'auth',
    'analytics',
    'dashboards',
    'governance',
    'inventory',
    'kubernetes_operations',
}
RETIRED_FUNCTIONAL_ROOTS = {
    'analytics',
    'dashboards',
    'governance',
    'inventory',
    'jobs',
    'kubernetes_operations',
}
RETIRED_CONTRACT_ROOTS = {
    'auth',
    'governance',
    'inventory',
    'jobs',
    'kubernetes_operations',
    'notifications',
}
REQUIRED_DOMAIN_PATHS = (
    'tests/access',
    'tests/integrations',
    'tests/kubernetes/analytics',
    'tests/kubernetes/dashboard',
    'tests/kubernetes/governance',
    'tests/kubernetes/inventory',
    'tests/kubernetes/operations',
    'tests/storage/object_storage/analytics',
    'tests/storage/object_storage/inventory',
    'tests/platform_operations/jobs',
    'tests/contracts/access/authentication',
    'tests/contracts/kubernetes/governance',
    'tests/contracts/kubernetes/operations',
    'tests/contracts/storage/object_storage/inventory',
    'tests/contracts/platform_operations/jobs',
    'tests/contracts/platform_operations/notifications',
)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    tests = root / 'tests'

    for name in sorted(RETIRED_FUNCTIONAL_ROOTS):
        if (tests / name).exists():
            errors.append(f'retired functional test root still exists: tests/{name}')

    for bucket in PURPOSE_BUCKETS:
        bucket_path = tests / bucket
        for name in sorted(RETIRED_PURPOSE_CHILDREN):
            if (bucket_path / name).exists():
                errors.append(f'retired {bucket} test domain still exists: tests/{bucket}/{name}')

    contracts = tests / 'contracts'
    for name in sorted(RETIRED_CONTRACT_ROOTS):
        if (contracts / name).exists():
            errors.append(f'retired contract domain still exists: tests/contracts/{name}')

    if (tests / 'debug' / 'inventory').exists():
        errors.append('retired debug domain still exists: tests/debug/inventory')

    for relative in REQUIRED_DOMAIN_PATHS:
        if not (root / relative).exists():
            errors.append(f'canonical test-domain path is missing: {relative}')

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print('FAIL — KAORI Test Domain Architecture')
        for error in errors:
            print(f'- {error}')
        return 1

    test_modules = len(list(TESTS.rglob('test_*.py')))
    print(f'PASS — KAORI Test Domain Architecture · {test_modules} test modules')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
