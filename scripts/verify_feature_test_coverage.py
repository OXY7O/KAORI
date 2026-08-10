#!/usr/bin/env python3
"""Require permanent release evidence across reviewed KAORI test layers."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

_REQUIRED_TEST_FILES = {
    'tests/unit/welcome/test_welcome_target_resolution.py': 3,
    'tests/welcome/test_welcome_characterization.py': 4,
    'tests/security/welcome/test_welcome_security.py': 3,
    'tests/rendering/welcome/test_welcome_rendering.py': 2,
    'tests/e2e/welcome/test_welcome_smoke.py': 2,
    'tests/dashboards/test_kubernetes_dashboard_characterization.py': 7,
    'tests/unit/dashboards/test_kubernetes_dashboard_domain.py': 3,
    'tests/security/dashboards/test_kubernetes_dashboard_security.py': 3,
    'tests/rendering/dashboards/test_kubernetes_dashboard_rendering.py': 2,
    'tests/integration/dashboards/test_kubernetes_dashboard_repository.py': 1,
    'tests/e2e/dashboards/test_kubernetes_dashboard_smoke.py': 2,
    'tests/contracts/kubernetes/test_inventory_final_release_contract.py': 4,
    'tests/unit/inventory/test_inventory_topology_selection.py': 3,
    'tests/inventory/test_inventory_route_characterization.py': 3,
    'tests/security/inventory/test_inventory_security.py': 3,
    'tests/rendering/inventory/test_inventory_rendering.py': 2,
    'tests/integration/inventory/test_node_inventory_read_model.py': 1,
    'tests/e2e/inventory/test_inventory_smoke.py': 2,
    'tests/contracts/governance/test_governance_final_release_contract.py': 4,
    'tests/unit/governance/test_tls_governance_policy.py': 3,
    'tests/governance/test_tls_governance_route_characterization.py': 3,
    'tests/security/governance/test_tls_governance_security.py': 3,
    'tests/rendering/governance/test_tls_governance_rendering.py': 2,
    'tests/integration/governance/test_tls_certificate_read_model.py': 1,
    'tests/e2e/governance/test_tls_governance_smoke.py': 2,
    'tests/contracts/kubernetes_operations/test_kubernetes_operations_final_release_contract.py': 4,
    'tests/unit/kubernetes_operations/test_operation_flow.py': 3,
    'tests/kubernetes_operations/test_route_authorization_characterization.py': 3,
    'tests/security/kubernetes_operations/test_kubernetes_operations_security.py': 3,
    'tests/rendering/kubernetes_operations/test_kubernetes_operations_rendering.py': 2,
    'tests/integration/kubernetes_operations/test_live_runtime_boundary.py': 1,
    'tests/e2e/kubernetes_operations/test_kubernetes_operations_smoke.py': 2,
}


def _test_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
    ]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, minimum_tests in _REQUIRED_TEST_FILES.items():
        path = root / relative_path
        if not path.exists():
            errors.append(f'{relative_path}: required release-test module is missing')
            continue
        try:
            tests = _test_functions(path)
        except SyntaxError as exc:
            errors.append(f'{relative_path}:{exc.lineno}: invalid Python test module')
            continue
        if len(tests) < minimum_tests:
            errors.append(f'{relative_path}: {len(tests)} behavior tests found; at least {minimum_tests} are required')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate permanent release-test coverage for reviewed KAORI domains.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()

    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(f'KAORI release-test coverage is present across {len(_REQUIRED_TEST_FILES)} required test modules.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
