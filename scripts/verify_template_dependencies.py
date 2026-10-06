#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / 'app' / 'templates'

_LITERAL_DEPENDENCY_PATTERNS = (
    re.compile(r"""{%\s*(?:extends|include|import)\s+["']([^"']+)["']"""),
    re.compile(r"""{%\s*from\s+["']([^"']+)["']\s+import\b"""),
)


def _dependencies(source: str) -> tuple[str, ...]:
    found: set[str] = set()
    for pattern in _LITERAL_DEPENDENCY_PATTERNS:
        found.update(match.group(1).strip() for match in pattern.finditer(source))
    return tuple(sorted(item for item in found if item))


def verify() -> None:
    templates = sorted(TEMPLATE_ROOT.rglob('*.html'))
    if not templates:
        raise AssertionError('No Jinja templates found under app/templates')

    checked_references = 0
    missing: list[str] = []
    invalid: list[str] = []

    for template in templates:
        source = template.read_text(encoding='utf-8')
        relative = template.relative_to(TEMPLATE_ROOT)
        for dependency in _dependencies(source):
            checked_references += 1
            candidate = Path(dependency)
            if candidate.is_absolute() or '..' in candidate.parts:
                invalid.append(f'{relative}: invalid template dependency {dependency!r}')
                continue
            if not (TEMPLATE_ROOT / candidate).is_file():
                missing.append(f'{relative}: missing template dependency {dependency!r}')

    problems = [*invalid, *missing]
    if problems:
        details = '\n'.join(f'- {item}' for item in problems)
        raise AssertionError(f'Jinja template dependency verification failed:\n{details}')

    print(f'PASS — KAORI Template Dependencies · {len(templates)} templates · {checked_references} literal references')


if __name__ == '__main__':
    verify()
