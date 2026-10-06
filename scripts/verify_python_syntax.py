#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tokenize
from pathlib import Path

_DEFAULT_ROOTS = ('app', 'migrations', 'tests', 'scripts')


def validate(root: Path, source_roots: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    for source_root in source_roots:
        base = root / source_root
        if not base.exists():
            errors.append(f'missing Python source root: {source_root}')
            continue
        for path in sorted(base.rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            try:
                with tokenize.open(path) as handle:
                    source = handle.read()
                compile(source, str(path), 'exec', dont_inherit=True)
            except (OSError, SyntaxError, UnicodeError) as exc:
                errors.append(f'{path.relative_to(root)}: {exc}')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Compile KAORI Python source in memory without creating bytecode artifacts.'
    )
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('source_roots', nargs='*', default=_DEFAULT_ROOTS)
    args = parser.parse_args()

    root = args.root.resolve()
    source_roots = tuple(args.source_roots) or _DEFAULT_ROOTS
    errors = validate(root, source_roots)
    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    count = sum(
        1
        for source_root in source_roots
        for path in (root / source_root).rglob('*.py')
        if '__pycache__' not in path.parts
    )
    print(f'KAORI Python syntax is valid across {count} source files without writing bytecode.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
