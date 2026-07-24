#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
from collections import defaultdict
from pathlib import Path

_MODULE_TOKEN = re.compile(r'^app(?:\.[A-Za-z_][A-Za-z0-9_]*)+$')


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root.parent).with_suffix('')
    parts = list(relative.parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def _resolved_from_import(current: str, path: Path, node: ast.ImportFrom) -> str:
    target = node.module or ''
    if not node.level:
        return target
    current_parts = current.split('.')
    package_parts = current_parts if path.name == '__init__.py' else current_parts[:-1]
    base_parts = package_parts[: max(len(package_parts) - node.level + 1, 0)]
    return '.'.join([*base_parts, target] if target else base_parts)


def _module_prefix(value: str, modules: set[str]) -> str | None:
    candidate = value
    while candidate.startswith('app.'):
        if candidate in modules:
            return candidate
        candidate = candidate.rsplit('.', 1)[0]
    return None


def validate(root: Path) -> list[str]:
    app_root = root / 'app'
    module_paths: dict[str, Path] = {}
    for path in sorted(app_root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        module_paths[_module_name(app_root, path)] = path
    modules = set(module_paths)
    incoming: dict[str, set[str]] = defaultdict(set)

    for source_root in ('app', 'tests', 'scripts', 'migrations'):
        for path in sorted((root / source_root).rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except SyntaxError as exc:
                return [f'{path.relative_to(root)}:{exc.lineno}: {exc.msg}']

            current = _module_name(app_root, path) if path.is_relative_to(app_root) else ''
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target = _module_prefix(alias.name, modules)
                        if target:
                            incoming[target].add(path.relative_to(root).as_posix())
                elif isinstance(node, ast.ImportFrom):
                    target_module = _resolved_from_import(current, path, node)
                    target = _module_prefix(target_module, modules)
                    if target:
                        incoming[target].add(path.relative_to(root).as_posix())
                    for alias in node.names:
                        target = _module_prefix(f'{target_module}.{alias.name}', modules)
                        if target:
                            incoming[target].add(path.relative_to(root).as_posix())
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value.strip()
                    if _MODULE_TOKEN.match(value):
                        target = _module_prefix(value, modules)
                        if target:
                            incoming[target].add(path.relative_to(root).as_posix())

    errors: list[str] = []
    for module, path in sorted(module_paths.items()):
        if path.name == '__init__.py':
            continue
        if incoming.get(module):
            continue
        errors.append(f'{path.relative_to(root)} has no importer, configured entrypoint, test, or script consumer')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Reject unreachable KAORI Python modules.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    root = args.root.resolve()

    errors = validate(root)
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    modules = sum(1 for path in (root / 'app').rglob('*.py') if '__pycache__' not in path.parts)
    print(f'KAORI module reachability is closed across {modules} application modules.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
