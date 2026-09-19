from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / 'tests'
SOURCE_SEGMENTS = {'app', 'migrations', 'scripts'}

RETIRED_TEST_REFERENCES = {
    'has_prometheus_data': 'use has_metrics_source_data',
    'prometheus_cluster_ids': 'use metrics_source_cluster_ids',
    '_prometheus_dataset_eligible': 'use _metrics_source_dataset_eligible',
    "templates' / 'inventory' / 'kubernetes": 'use app/templates/kubernetes/inventory',
    "ROOT / 'app/templates/analytics'": 'use app/templates/kubernetes/analytics for Kubernetes analytics rendering tests',
}


def _evaluate_path(node: ast.AST, env: dict[str, Path], test_file: Path) -> Path | str | None:
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _evaluate_path(node.left, env, test_file)
        right = _evaluate_path(node.right, env, test_file)
        if isinstance(left, Path) and isinstance(right, str):
            return left / right
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'Path'
        and len(node.args) == 1
    ):
        arg = node.args[0]
        if isinstance(arg, ast.Name) and arg.id == '__file__':
            return test_file.resolve()
        value = _evaluate_path(arg, env, test_file)
        if isinstance(value, str):
            return Path(value)
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'resolve':
        value = _evaluate_path(node.func.value, env, test_file)
        if isinstance(value, Path):
            return value.resolve()
        return None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents':
        value = _evaluate_path(node.value.value, env, test_file)
        if not isinstance(value, Path):
            return None
        try:
            index = ast.literal_eval(node.slice)
        except (ValueError, TypeError):
            return None
        if isinstance(index, int) and 0 <= index < len(value.parents):
            return value.parents[index]
    return None


def _top_level_paths(test_file: Path) -> dict[str, Path]:
    tree = ast.parse(test_file.read_text(encoding='utf-8'), filename=str(test_file))
    env: dict[str, Path] = {}
    for node in tree.body:
        target: ast.AST | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        resolved = _evaluate_path(value, env, test_file)
        if isinstance(resolved, Path):
            env[target.id] = resolved
    return env


def _is_source_reference(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    if not relative.parts:
        return False
    if relative.parts[0] in SOURCE_SEGMENTS:
        return True
    return path.suffix in {'.py', '.html', '.js', '.yaml', '.yml', '.json'}


def main() -> int:
    errors: list[str] = []
    for test_file in sorted(TESTS_ROOT.rglob('*.py')):
        if 'contracts' in test_file.relative_to(TESTS_ROOT).parts:
            continue
        try:
            paths = _top_level_paths(test_file)
        except (OSError, SyntaxError) as exc:
            errors.append(f'{test_file.relative_to(ROOT)}: unable to inspect test paths: {exc}')
            continue
        for name, path in sorted(paths.items()):
            if _is_source_reference(path) and not path.exists():
                errors.append(f'{test_file.relative_to(ROOT)}: {name} points to missing path {path.relative_to(ROOT)}')

        source = test_file.read_text(encoding='utf-8')
        for retired, replacement in RETIRED_TEST_REFERENCES.items():
            if retired in source:
                errors.append(f'{test_file.relative_to(ROOT)}: retired test reference {retired!r}; {replacement}')

    if errors:
        print('FAIL — KAORI Runtime Test Source Paths')
        for error in errors:
            print(f'- {error}')
        return 1

    print('PASS — KAORI Runtime Test Source Paths')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
