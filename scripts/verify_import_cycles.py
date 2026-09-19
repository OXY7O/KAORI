#!/usr/bin/env python3
"""Reject runtime import cycles across KAORI application modules.

Imports guarded by ``if TYPE_CHECKING`` are excluded because they are not
executed at runtime. Relative imports are resolved from the importing module or
package so package ``__init__`` files are handled correctly.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / 'app'


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    path: Path
    is_package: bool


def _discover_modules() -> dict[str, ModuleInfo]:
    modules: dict[str, ModuleInfo] = {}
    for path in APP_ROOT.rglob('*.py'):
        relative = path.relative_to(PROJECT_ROOT).with_suffix('')
        parts = list(relative.parts)
        is_package = path.name == '__init__.py'
        if is_package:
            parts.pop()
        name = '.'.join(parts)
        modules[name] = ModuleInfo(name=name, path=path, is_package=is_package)
    return modules


def _is_type_checking_guard(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == 'TYPE_CHECKING'
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == 'typing'
        and node.attr == 'TYPE_CHECKING'
    )


def _resolve_relative_import(
    *,
    current: ModuleInfo,
    level: int,
    imported_module: str | None,
) -> str:
    package = current.name if current.is_package else current.name.rpartition('.')[0]
    parts = package.split('.') if package else []
    upward_steps = level - 1
    if upward_steps:
        parts = parts[:-upward_steps]
    if imported_module:
        parts.extend(imported_module.split('.'))
    return '.'.join(parts)


def _runtime_imports(module: ModuleInfo, known_modules: set[str]) -> set[str]:
    tree = ast.parse(module.path.read_text(encoding='utf-8'), filename=str(module.path))
    imports: set[str] = set()

    class RuntimeImportVisitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If) -> None:  # noqa: N802 - ast visitor API
            if _is_type_checking_guard(node.test):
                for statement in node.orelse:
                    self.visit(statement)
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - ast visitor API
            for alias in node.names:
                if alias.name == 'app' or alias.name.startswith('app.'):
                    imports.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802 - ast visitor API
            target = (
                _resolve_relative_import(
                    current=module,
                    level=node.level,
                    imported_module=node.module,
                )
                if node.level
                else (node.module or '')
            )
            if target != 'app' and not target.startswith('app.'):
                return
            imports.add(target)
            for alias in node.names:
                candidate = f'{target}.{alias.name}'
                if candidate in known_modules:
                    imports.add(candidate)

    RuntimeImportVisitor().visit(tree)
    return imports


def _nearest_known_module(name: str, known_modules: set[str]) -> str | None:
    candidate = name
    while candidate:
        if candidate in known_modules:
            return candidate
        candidate = candidate.rpartition('.')[0]
    return None


def _build_graph(modules: dict[str, ModuleInfo]) -> dict[str, set[str]]:
    known_modules = set(modules)
    graph = {name: set() for name in modules}
    for name, module in modules.items():
        for imported_name in _runtime_imports(module, known_modules):
            dependency = _nearest_known_module(imported_name, known_modules)
            if dependency and dependency != name:
                graph[name].add(dependency)
    return graph


def _strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    next_index = 0
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal next_index
        indices[node] = next_index
        low_links[node] = next_index
        next_index += 1
        stack.append(node)
        on_stack.add(node)

        for dependency in graph[node]:
            if dependency not in indices:
                visit(dependency)
                low_links[node] = min(low_links[node], low_links[dependency])
            elif dependency in on_stack:
                low_links[node] = min(low_links[node], indices[dependency])

        if low_links[node] != indices[node]:
            return

        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1:
            components.append(sorted(component))

    for node in graph:
        if node not in indices:
            visit(node)

    return sorted(components, key=lambda item: (-len(item), item))


def main() -> int:
    modules = _discover_modules()
    graph = _build_graph(modules)
    cycles = _strongly_connected_components(graph)
    if cycles:
        print('ERROR: runtime import cycles detected:', file=sys.stderr)
        for cycle in cycles:
            print(f'  - {" -> ".join(cycle)}', file=sys.stderr)
        return 1

    edge_count = sum(len(edges) for edges in graph.values())
    print(f'KAORI runtime import graph is acyclic across {len(modules)} modules and {edge_count} dependency edges.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
