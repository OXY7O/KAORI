#!/usr/bin/env python3
"""Validate KAORI visible Title Case for reviewed and locked UI scopes.

The scope list expands only after a workspace completes manual pre-release review.
Narrative copy is intentionally excluded; headings, table headers, form labels,
and button labels are checked. Technical/Jinja-driven values are skipped.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_TEMPLATE_ROOTS = (
    ROOT / 'app' / 'templates' / 'welcome',
    ROOT / 'app' / 'templates' / 'dashboards' / 'kubernetes',
)
CHECKED_TAGS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th', 'label', 'button')
MINOR_WORDS = {
    'a',
    'an',
    'and',
    'as',
    'at',
    'but',
    'by',
    'for',
    'from',
    'in',
    'nor',
    'of',
    'on',
    'or',
    'per',
    'the',
    'to',
    'via',
    'with',
    'without',
}
_TAG_PATTERN = re.compile(
    rf'<(?P<tag>{"|".join(CHECKED_TAGS)})\b[^>]*>(?P<body>.*?)</(?P=tag)>',
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG = re.compile(r'<[^>]+>')
_JINJA_BLOCK = re.compile(r'{[%#].*?[%#]}', re.DOTALL)
_JINJA_EXPR = re.compile(r'{{.*?}}', re.DOTALL)
_WORD = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:[-/&][A-Za-z0-9]+)*')


def _visible_static_text(body: str) -> str:
    value = _JINJA_BLOCK.sub(' ', body)
    value = _JINJA_EXPR.sub(' ', value)
    value = _HTML_TAG.sub(' ', value)
    return ' '.join(html.unescape(value).split())


def _is_capitalized_or_technical(word: str) -> bool:
    parts = re.split(r'[-/&]', word)
    return all(not part or part[0].isdigit() or part[0].isupper() or part.isupper() for part in parts)


def _title_case_error(text: str) -> str | None:
    words = _WORD.findall(text)
    if not words:
        return None

    for index, word in enumerate(words):
        lowered = word.lower()
        is_internal = 0 < index < len(words) - 1
        if is_internal and lowered in MINOR_WORDS:
            if word != lowered:
                return f'minor word {word!r} must be lowercase'
            continue
        if not _is_capitalized_or_technical(word):
            return f'word {word!r} must start with an uppercase letter'
    return None


def verify() -> None:
    failures: list[str] = []
    checked = 0
    for template_root in REVIEWED_TEMPLATE_ROOTS:
        if not template_root.exists():
            raise AssertionError(f'Missing reviewed template root: {template_root.relative_to(ROOT)}')
        for path in sorted(template_root.rglob('*.html')):
            source = path.read_text(encoding='utf-8')
            for match in _TAG_PATTERN.finditer(source):
                text = _visible_static_text(match.group('body'))
                if not text:
                    continue
                checked += 1
                error = _title_case_error(text)
                if error:
                    line = source.count('\n', 0, match.start()) + 1
                    failures.append(f'{path.relative_to(ROOT)}:{line}: {text!r}: {error}')

    if failures:
        raise AssertionError('KAORI Title Case violations:\n' + '\n'.join(failures))

    print(
        f'KAORI Title Case standard passed for {checked} static reviewed labels across '
        'Welcome and Kubernetes Dashboard; internal English minor words remain lowercase.'
    )


if __name__ == '__main__':
    verify()
