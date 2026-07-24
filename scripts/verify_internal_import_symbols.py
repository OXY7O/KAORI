#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModuleInfo:
    path: Path
    symbols: frozenset[str]
    has_dynamic_getattr: bool


def _module_name(app_root: Path, path: Path) -> str:
    relative = path.relative_to(app_root.parent).with_suffix('')
    parts = list(relative.parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: set[str] = set()
    for target in targets:
        for child in ast.walk(target):
            if isinstance(child, ast.Name):
                names.add(child.id)
    return names


def _module_info(path: Path) -> ModuleInfo:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    symbols: set[str] = set()
    has_dynamic_getattr = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.add(node.name)
            has_dynamic_getattr |= node.name == '__getattr__'
        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.add(alias.asname or alias.name.split('.', 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    symbols.add(alias.asname or alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            symbols.update(_assigned_names(node))
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            symbols.add(node.name.id)
    return ModuleInfo(path=path, symbols=frozenset(symbols), has_dynamic_getattr=has_dynamic_getattr)


def _resolve_from(current: str, path: Path, node: ast.ImportFrom) -> str:
    target = node.module or ''
    if not node.level:
        return target
    current_parts = current.split('.')
    package_parts = current_parts if path.name == '__init__.py' else current_parts[:-1]
    base_parts = package_parts[: max(len(package_parts) - node.level + 1, 0)]
    return '.'.join([*base_parts, target] if target else base_parts)


def validate(root: Path) -> list[str]:
    app_root = root / 'app'
    modules: dict[str, ModuleInfo] = {}
    for path in sorted(app_root.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        modules[_module_name(app_root, path)] = _module_info(path)

    errors: list[str] = []
    for source_root in ('app', 'tests', 'scripts', 'migrations'):
        for path in sorted((root / source_root).rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            current = _module_name(app_root, path) if path.is_relative_to(app_root) else ''
            relative = path.relative_to(root).as_posix()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not alias.name.startswith('app.'):
                            continue
                        if alias.name not in modules:
                            errors.append(f'{relative}:{node.lineno}: internal module {alias.name!r} does not exist')
                elif isinstance(node, ast.ImportFrom):
                    target = _resolve_from(current, path, node)
                    if target != 'app' and not target.startswith('app.'):
                        continue
                    info = modules.get(target)
                    if info is None:
                        errors.append(f'{relative}:{node.lineno}: internal import module {target!r} does not exist')
                        continue
                    if info.has_dynamic_getattr:
                        continue
                    for alias in node.names:
                        if alias.name == '*':
                            continue
                        if alias.name in info.symbols:
                            continue
                        if f'{target}.{alias.name}' in modules:
                            continue
                        errors.append(f'{relative}:{node.lineno}: {alias.name!r} is not exported by {target!r}')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate that every internal KAORI import module and symbol exists.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        errors = validate(root)
    except (OSError, SyntaxError, UnicodeError) as exc:
        print(f'ERROR: {exc}')
        return 1
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    imports = 0
    for source_root in ('app', 'tests', 'scripts', 'migrations'):
        for path in (root / source_root).rglob('*.py'):
            if '__pycache__' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            imports += sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    print(f'KAORI internal import modules and symbols are valid across {imports} import statements.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
