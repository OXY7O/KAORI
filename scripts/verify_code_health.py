#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODULE_LINES = 800
DEFAULT_FUNCTION_LINES = 160
DEFAULT_BRANCH_POINTS = 30
DEFAULT_ARGUMENTS = 8


@dataclass(frozen=True, slots=True)
class FunctionMetric:
    key: str
    lines: int
    branches: int
    arguments: int


def _function_key(path: Path, parents: tuple[str, ...], name: str) -> str:
    qualified = '.'.join((*parents, name))
    return f'{path.as_posix()}::{qualified}'


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


def _walk_functions(path: Path, tree: ast.Module) -> list[FunctionMetric]:
    metrics: list[FunctionMetric] = []

    def visit(body: list[ast.stmt], parents: tuple[str, ...]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = node.end_lineno or node.lineno
                metrics.append(
                    FunctionMetric(
                        key=_function_key(path, parents, node.name),
                        lines=end - node.lineno + 1,
                        branches=_branch_points(node),
                        arguments=_argument_count(node),
                    )
                )
                visit(node.body, (*parents, node.name))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, (*parents, node.name))

    visit(tree.body, ())
    return metrics


def scan(app_root: Path) -> tuple[dict[str, int], dict[str, FunctionMetric], int]:
    module_lines: dict[str, int] = {}
    functions: dict[str, FunctionMetric] = {}
    broad_exceptions = 0

    for path in sorted(app_root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        source = path.read_text(encoding='utf-8')
        relative = path.as_posix()
        module_lines[relative] = len(source.splitlines())
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            raise ValueError(f'{relative}:{exc.lineno}: cannot parse source: {exc.msg}') from exc
        for metric in _walk_functions(path, tree):
            functions[metric.key] = metric
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                broad_exceptions += 1
            elif isinstance(node.type, ast.Name) and node.type.id in {'Exception', 'BaseException'}:
                broad_exceptions += 1

    return module_lines, functions, broad_exceptions


def build_baseline(app_root: Path) -> dict[str, object]:
    modules, functions, broad_exceptions = scan(app_root)
    return {
        'defaults': {
            'module_lines': DEFAULT_MODULE_LINES,
            'function_lines': DEFAULT_FUNCTION_LINES,
            'branch_points': DEFAULT_BRANCH_POINTS,
            'arguments': DEFAULT_ARGUMENTS,
        },
        'module_line_limits': {key: value for key, value in sorted(modules.items()) if value > DEFAULT_MODULE_LINES},
        'function_line_limits': {
            key: metric.lines for key, metric in sorted(functions.items()) if metric.lines > DEFAULT_FUNCTION_LINES
        },
        'function_branch_limits': {
            key: metric.branches for key, metric in sorted(functions.items()) if metric.branches > DEFAULT_BRANCH_POINTS
        },
        'function_argument_limits': {
            key: metric.arguments for key, metric in sorted(functions.items()) if metric.arguments > DEFAULT_ARGUMENTS
        },
        'broad_exception_limit': broad_exceptions,
    }


def _validate_metric(
    *,
    label: str,
    current: dict[str, int],
    baseline: dict[str, int],
    default_limit: int,
) -> list[str]:
    errors: list[str] = []
    for key, value in sorted(current.items()):
        allowed = int(baseline.get(key, default_limit))
        if value > allowed:
            errors.append(f'{key}: {label} {value} exceeds allowed {allowed}')
    for key in sorted(baseline):
        if key not in current:
            errors.append(f'{key}: stale {label} debt entry; remove it from the baseline')
        elif current[key] <= default_limit:
            errors.append(f'{key}: resolved {label} debt; remove it from the baseline')
    return errors


def validate(app_root: Path, baseline_path: Path) -> list[str]:
    payload = json.loads(baseline_path.read_text(encoding='utf-8'))
    defaults = payload.get('defaults', {})
    module_limit = int(defaults.get('module_lines', DEFAULT_MODULE_LINES))
    function_limit = int(defaults.get('function_lines', DEFAULT_FUNCTION_LINES))
    branch_limit = int(defaults.get('branch_points', DEFAULT_BRANCH_POINTS))
    argument_limit = int(defaults.get('arguments', DEFAULT_ARGUMENTS))

    modules, functions, broad_exceptions = scan(app_root)
    errors = _validate_metric(
        label='module lines',
        current=modules,
        baseline={str(key): int(value) for key, value in payload.get('module_line_limits', {}).items()},
        default_limit=module_limit,
    )
    errors += _validate_metric(
        label='function lines',
        current={key: metric.lines for key, metric in functions.items()},
        baseline={str(key): int(value) for key, value in payload.get('function_line_limits', {}).items()},
        default_limit=function_limit,
    )
    errors += _validate_metric(
        label='branch points',
        current={key: metric.branches for key, metric in functions.items()},
        baseline={str(key): int(value) for key, value in payload.get('function_branch_limits', {}).items()},
        default_limit=branch_limit,
    )
    errors += _validate_metric(
        label='arguments',
        current={key: metric.arguments for key, metric in functions.items()},
        baseline={str(key): int(value) for key, value in payload.get('function_argument_limits', {}).items()},
        default_limit=argument_limit,
    )
    broad_limit = int(payload.get('broad_exception_limit', 0))
    if broad_exceptions > broad_limit:
        errors.append(
            f'app: broad exception handlers {broad_exceptions} exceed allowed {broad_limit}; catch explicit boundary errors'
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Prevent KAORI maintainability debt from expanding.')
    parser.add_argument('--app-root', type=Path, default=Path('app'))
    parser.add_argument(
        '--baseline',
        type=Path,
        default=Path('docs/architecture/code-health-debt-baseline.json'),
    )
    parser.add_argument('--write-baseline', action='store_true')
    args = parser.parse_args()

    try:
        if args.write_baseline:
            payload = build_baseline(args.app_root)
            args.baseline.parent.mkdir(parents=True, exist_ok=True)
            args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            print(f'Wrote KAORI code-health baseline to {args.baseline}.')
            return 0
        errors = validate(args.app_root, args.baseline)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}')
        return 1

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    modules, functions, broad_exceptions = scan(args.app_root)
    print(
        'KAORI code-health debt is bounded across '
        f'{len(modules)} modules and {len(functions)} functions; '
        f'{broad_exceptions} broad exception handlers remain in the burn-down baseline.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
