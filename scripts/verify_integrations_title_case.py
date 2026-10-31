#!/usr/bin/env python3
"""Validate KAORI Title Case across reviewed Integration provider templates."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_TEMPLATE_ROOTS = (ROOT / 'app' / 'templates' / 'integrations',)
CHECKED_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th', 'label', 'button'}
TECHNICAL_WORDS = {'ntfy'}  # Official lowercase provider brand; not a generic casing exemption.
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
    if word in TECHNICAL_WORDS:
        return True
    parts = re.split(r'[-/&]', word)
    return all(not part or part[0].isdigit() or part[0].isupper() or part.isupper() for part in parts)


def _title_case_error(text: str) -> str | None:
    words = WORD.findall(text)
    for index, word in enumerate(words):
        # Preserve the canonical Vault KV v2 technical version, not a generic casing waiver.
        if word == 'v2' and index > 0 and words[index - 1] == 'KV':
            continue
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
        self.checkbox_label_lines: set[int] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'input' and ('type', 'checkbox') in attrs:
            self.checkbox_label_lines.update(line for label_tag, line, _ in self._stack if label_tag == 'label')
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
            # WTForms renders checkbox markup via Jinja, not literal <input> HTML here.
            # Apply the approved full-sentence consent exception only to this known checkbox.
            if '{{ form.pki_stored_certs_enabled(' in data:
                self.checkbox_label_lines.update(line for tag, line, _ in self._stack if tag == 'label')
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
                # Full-sentence checkbox consent is body copy, not a Title Case heading.
                if line in parser.checkbox_label_lines and '. ' in text:
                    continue
                checked += 1
                error = _title_case_error(text)
                if error:
                    failures.append(f'{path.relative_to(ROOT)}:{line}: {text!r}: {error}')

    if failures:
        raise AssertionError('KAORI Integrations Title Case violations:\n' + '\n'.join(failures))

    print(f'KAORI Integrations Title Case passed for {checked} static headings, headers, labels, and buttons.')


if __name__ == '__main__':
    verify()
