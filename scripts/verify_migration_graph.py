#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


MAX_ALEMBIC_REVISION_LENGTH = 32


@dataclass(frozen=True)
class MigrationRevision:
    path: Path
    revision: str
    down_revisions: tuple[str, ...]


def _literal_assignment(module: ast.Module, name: str) -> object:
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value is not None:
                return ast.literal_eval(node.value)
    raise ValueError(f'missing {name!r} assignment')


def _normalize_down_revisions(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f'unsupported down_revision value: {value!r}')


def load_migrations(versions_dir: Path) -> list[MigrationRevision]:
    revisions: list[MigrationRevision] = []
    for path in sorted(versions_dir.glob('*.py')):
        if path.name == '__init__.py':
            continue
        try:
            module = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            revision = _literal_assignment(module, 'revision')
            down_revision = _literal_assignment(module, 'down_revision')
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f'{path}: {exc}') from exc

        if not isinstance(revision, str) or not revision.strip():
            raise ValueError(f'{path}: revision must be a non-empty string')
        if len(revision) > MAX_ALEMBIC_REVISION_LENGTH:
            raise ValueError(
                f'{path}: revision {revision!r} is {len(revision)} characters; '
                f'Alembic version_num supports at most {MAX_ALEMBIC_REVISION_LENGTH}'
            )

        revisions.append(
            MigrationRevision(
                path=path,
                revision=revision,
                down_revisions=_normalize_down_revisions(down_revision),
            )
        )
    return revisions


def validate_graph(revisions: Iterable[MigrationRevision]) -> tuple[list[str], list[str], list[str]]:
    revisions = list(revisions)
    errors: list[str] = []
    by_revision: dict[str, MigrationRevision] = {}

    for item in revisions:
        previous = by_revision.get(item.revision)
        if previous is not None:
            errors.append(f'duplicate revision {item.revision!r}: {previous.path} and {item.path}')
            continue
        by_revision[item.revision] = item

    children: dict[str, set[str]] = {revision: set() for revision in by_revision}
    for item in revisions:
        for parent in item.down_revisions:
            if parent == item.revision:
                errors.append(f'{item.path}: revision cannot reference itself')
                continue
            if parent not in by_revision:
                errors.append(f'{item.path}: down_revision {parent!r} does not exist in migrations/versions')
                continue
            children[parent].add(item.revision)

    roots = sorted(item.revision for item in revisions if not item.down_revisions)
    heads = sorted(revision for revision, descendants in children.items() if not descendants)

    if len(roots) != 1:
        errors.append(f'expected exactly one migration root, found {len(roots)}: {roots}')
    if len(heads) != 1:
        errors.append(f'expected exactly one migration head, found {len(heads)}: {heads}')

    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(revision: str) -> None:
        marker = state.get(revision, 0)
        if marker == 2:
            return
        if marker == 1:
            cycle_start = stack.index(revision) if revision in stack else 0
            cycle = [*stack[cycle_start:], revision]
            errors.append(f'migration cycle detected: {" -> ".join(cycle)}')
            return

        state[revision] = 1
        stack.append(revision)
        for child in sorted(children.get(revision, ())):
            visit(child)
        stack.pop()
        state[revision] = 2

    for revision in sorted(by_revision):
        visit(revision)

    return errors, roots, heads


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate the KAORI Alembic revision graph without a database.')
    parser.add_argument(
        '--versions-dir',
        type=Path,
        default=Path('migrations/versions'),
        help='Directory containing Alembic revision modules.',
    )
    args = parser.parse_args()

    try:
        revisions = load_migrations(args.versions_dir)
        errors, roots, heads = validate_graph(revisions)
    except ValueError as exc:
        print(f'ERROR: {exc}')
        return 1

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(f'KAORI migration graph is valid: {len(revisions)} revisions, root={roots[0]}, head={heads[0]}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
