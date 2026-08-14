#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

MAX_MODULE_LINES = 800
MAX_FUNCTION_LINES = 160
MAX_BRANCH_POINTS = 30
MAX_ARGUMENTS = 8

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    Path('app/welcome'),
    Path('app/dashboards/kubernetes'),
    Path('app/inventory/kubernetes/overview.py'),
    Path('app/inventory/kubernetes/routes.py'),
    Path('app/inventory/kubernetes/topology'),
    Path('app/inventory/kubernetes/resources/nodes.py'),
    Path('app/inventory/kubernetes/resources/namespaces.py'),
    Path('app/inventory/kubernetes/collectors/configuration.py'),
    Path('app/inventory/kubernetes/resources/configuration.py'),
    Path('app/inventory/kubernetes/resources/configuration_semantics.py'),
    Path('app/inventory/kubernetes/resources/workloads.py'),
    Path('app/inventory/kubernetes/resources/pods.py'),
    Path('app/inventory/kubernetes/resources/pod_detail.py'),
    Path('app/inventory/kubernetes/resources/services.py'),
    Path('app/inventory/kubernetes/collectors/ingresses.py'),
    Path('app/inventory/kubernetes/resources/ingresses.py'),
    Path('app/inventory/kubernetes/resources/ingress_semantics.py'),
    Path('app/inventory/kubernetes/collectors/storage.py'),
    Path('app/inventory/kubernetes/resources/storage.py'),
    Path('app/inventory/kubernetes/resources/storage_semantics.py'),
    Path('app/kubernetes_operations/secrets'),
    Path('app/governance/tls_certificates/service.py'),
    Path('app/governance/tls_certificates/updates.py'),
    Path('app/governance/tls_certificates/mutation.py'),
)


def _python_files(target: Path) -> list[Path]:
    absolute = ROOT / target
    return sorted(absolute.rglob('*.py')) if absolute.is_dir() else [absolute]


def _branch_points(node: ast.AST) -> int:
    points = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Match)):
            points += 1
        elif isinstance(child, ast.BoolOp):
            points += max(1, len(child.values) - 1)
        elif isinstance(child, ast.Try):
            points += len(child.handlers) + int(bool(child.orelse)) + int(bool(child.finalbody))
        elif isinstance(child, ast.comprehension):
            points += 1 + len(child.ifs)
    return points


def _argument_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    args = node.args
    return (
        len(args.posonlyargs)
        + len(args.args)
        + len(args.kwonlyargs)
        + int(args.vararg is not None)
        + int(args.kwarg is not None)
    )


def _function_errors(path: Path, tree: ast.Module) -> list[str]:
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        lines = (node.end_lineno or node.lineno) - node.lineno + 1
        branches = _branch_points(node)
        arguments = _argument_count(node)
        label = f'{path.relative_to(ROOT)}::{node.name}'
        if lines > MAX_FUNCTION_LINES:
            errors.append(f'{label}: {lines} lines exceeds {MAX_FUNCTION_LINES}')
        if branches > MAX_BRANCH_POINTS:
            errors.append(f'{label}: {branches} branch points exceeds {MAX_BRANCH_POINTS}')
        if arguments > MAX_ARGUMENTS:
            errors.append(f'{label}: {arguments} arguments exceeds {MAX_ARGUMENTS}')
    return errors


def main() -> int:
    errors: list[str] = []
    checked = 0
    for target in TARGETS:
        for path in _python_files(target):
            checked += 1
            source = path.read_text(encoding='utf-8')
            if len(source.splitlines()) > MAX_MODULE_LINES:
                errors.append(f'{path.relative_to(ROOT)}: {len(source.splitlines())} lines exceeds {MAX_MODULE_LINES}')
            tree = ast.parse(source, filename=str(path))
            errors.extend(_function_errors(path, tree))

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print(f'PASS — KAORI Core Code Health · {checked} modules')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
