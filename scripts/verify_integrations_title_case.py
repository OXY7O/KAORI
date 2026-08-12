#!/usr/bin/env python3
"""Validate KAORI Title Case across reviewed Integration provider templates."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_TEMPLATE_ROOTS = (
    ROOT / 'app' / 'templates' / 'integrations',
    ROOT / 'app' / 'templates' / 'minio',
    ROOT / 'app' / 'templates' / 'prometheus',
    ROOT / 'app' / 'templates' / 'alertmanager',
)
CHECKED_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th', 'label', 'button'}
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
JINJA = re.compile(r'{{.*?}}|{%.*?%}|{#.*?#}', re.DOTALL)
WORD = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:[-/&][A-Za-z0-9]+)*')


def _is_capitalized_or_technical(word: str) -> bool:
    parts = re.split(r'[-/&]', word)
    return all(not part or part[0].isdigit() or part[0].isupper() or part.isupper() for part in parts)


def _title_case_error(text: str) -> str | None:
    words = WORD.findall(text)
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


class _VisibleLabelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[tuple[str, int, list[str]]] = []
        self.labels: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in CHECKED_TAGS:
            self._stack.append((tag, self.getpos()[0], []))
        elif self._stack:
            self._stack[-1][2].append(' ')

    def handle_endtag(self, tag: str) -> None:
        if not self._stack or self._stack[-1][0] != tag:
            return
        _, line, chunks = self._stack.pop()
        text = ' '.join(JINJA.sub(' ', ''.join(chunks)).split())
        if text:
            self.labels.append((line, text))

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1][2].append(data)


def verify() -> None:
    failures: list[str] = []
    checked = 0
    for template_root in REVIEWED_TEMPLATE_ROOTS:
        if not template_root.exists():
            raise AssertionError(f'Missing reviewed template root: {template_root.relative_to(ROOT)}')
        for path in sorted(template_root.rglob('*.html')):
            parser = _VisibleLabelParser()
            parser.feed(path.read_text(encoding='utf-8'))
            for line, text in parser.labels:
                checked += 1
                error = _title_case_error(text)
                if error:
                    failures.append(f'{path.relative_to(ROOT)}:{line}: {text!r}: {error}')

    if failures:
        raise AssertionError('KAORI Integrations Title Case violations:\n' + '\n'.join(failures))

    print(f'KAORI Integrations Title Case passed for {checked} static headings, headers, labels, and buttons.')


if __name__ == '__main__':
    verify()
