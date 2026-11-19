#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, TemplateSyntaxError, select_autoescape

_METRICS = ('inline_styles', 'inline_scripts', 'inline_event_handlers')
_EVENT_HANDLER = re.compile(
    r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=',
    re.IGNORECASE,
)
@dataclass
class _ScriptTag:
    start: int
    attributes: list[tuple[str, str | None]]
    raw_attributes: str
    body: str | None = None


class _ScriptTagParser(HTMLParser):
    """Inspect checked-in HTML source without regex-matching tag boundaries."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self._source = source
        self._line_starts = [0, *(index + 1 for index, char in enumerate(source) if char == '\n')]
        self._active: tuple[_ScriptTag, int] | None = None
        self.scripts: list[_ScriptTag] = []

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != 'script':
            return
        raw = self.get_starttag_text() or ''
        start = self._offset()
        script = _ScriptTag(start=start, attributes=attrs, raw_attributes=raw[len('<script') : -1].strip())
        self.scripts.append(script)
        self._active = (script, start + len(raw))

    def handle_endtag(self, tag: str) -> None:
        if tag != 'script' or self._active is None:
            return
        script, body_start = self._active
        script.body = self._source[body_start : self._offset()]
        self._active = None


def _parse_script_tags(source: str) -> list[_ScriptTag]:
    parser = _ScriptTagParser(source)
    parser.feed(source)
    parser.close()
    return parser.scripts


_APPROVED_INLINE_STYLE_COMPONENTS = {
    'app/templates/components/progress_bar.html',
    'app/templates/reports/pdf/components/analytics_publication.html',
}
_APPROVED_PREPAINT_BOOTSTRAPS = {
    'app/templates/layouts/app.html': {
        'marker': 'app-shell',
        'body': """
            ;(function () {
                const theme = localStorage.getItem('theme')
                const savedSidebarState = localStorage.getItem('kaori.sidebarExpanded')

                if (theme === 'dark') {
                    document.documentElement.classList.add('dark')
                }

                if (savedSidebarState === 'false') {
                    document.documentElement.classList.add('sidebar-collapsed')
                }
            })()
        """,
    },
    'app/templates/layouts/auth.html': {
        'marker': 'auth-theme',
        'body': """
            ;(function () {
                const storedTheme = localStorage.getItem('theme')

                if (storedTheme === 'dark') {
                    document.documentElement.classList.add('dark')
                }
            })()
        """,
    },
}


def _normalize_script_body(source: str) -> str:
    return re.sub(r'\\s+', ' ', source).strip()


def _approved_prepaint_script_starts(relative: str, source: str, scripts: list[_ScriptTag]) -> set[int]:
    contract = _APPROVED_PREPAINT_BOOTSTRAPS.get(relative)
    if contract is None:
        return set()

    head_end = source.lower().find('</head>')
    stylesheet = source.find("filename='css/output.css'")
    if head_end < 0 or stylesheet < 0:
        return set()

    expected_marker = str(contract['marker'])
    expected_attrs = f'data-kaori-prepaint-bootstrap="{expected_marker}"'
    expected_body = _normalize_script_body(str(contract['body']))
    approved: list[int] = []

    for script in scripts:
        marker = next(
            (value for name, value in script.attributes if name == 'data-kaori-prepaint-bootstrap'),
            None,
        )
        if marker != expected_marker:
            continue
        if script.raw_attributes != expected_attrs:
            continue
        if script.start >= head_end or script.start >= stylesheet:
            continue
        if script.body is None or _normalize_script_body(script.body) != expected_body:
            continue
        approved.append(script.start)

    return set(approved) if len(approved) == 1 else set()


def _metrics(relative: str, source: str) -> dict[str, int]:
    scripts = _parse_script_tags(source)
    approved_prepaint_starts = _approved_prepaint_script_starts(relative, source, scripts)
    return {
        'inline_styles': (
            0
            if relative in _APPROVED_INLINE_STYLE_COMPONENTS
            else len(re.findall(r'\bstyle\s*=', source, re.IGNORECASE))
        ),
        'inline_scripts': sum(
            1
            for script in scripts
            if not any(name == 'src' for name, _ in script.attributes)
            and not any(
                name == 'type' and value is not None and value.lower() == 'application/json'
                for name, value in script.attributes
            )
            and script.start not in approved_prepaint_starts
        ),
        'inline_event_handlers': len(_EVENT_HANDLER.findall(source)),
    }


def scan(root: Path) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for path in sorted((root / 'app' / 'templates').rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        relative = path.relative_to(root).as_posix()
        metrics = _metrics(relative, source)
        if any(metrics.values()):
            result[path.relative_to(root).as_posix()] = metrics
    return result


def _validate_component_ownership(root: Path) -> list[str]:
    errors: list[str] = []
    ownership_path = root / 'docs' / 'design' / 'components' / 'REUSABLE_COMPONENT_OWNERSHIP.md'
    if not ownership_path.exists():
        errors.append('reusable component ownership registry is missing')
        ownership = ''
    else:
        ownership = ownership_path.read_text(encoding='utf-8')

    required_ownership_tokens = (
        'Hero and context',
        'Readiness and operational callouts',
        'Tables, filters, loading, empty/error, and pagination',
        'Forms, action bars, and destructive confirmation',
        'Modal, drawer, and sheet surfaces',
        'Navigation and mobile action surfaces',
        'Operational toast and notification surfaces',
        'Framed Workspace Tabs',
        'Adapter rule',
    )
    for token in required_ownership_tokens:
        if token not in ownership:
            errors.append(f'reusable component ownership registry missing contract: {token}')

    for relative in ('docs/design/README.md', 'docs/design/DESIGN_SYSTEM.md'):
        path = root / relative
        source = path.read_text(encoding='utf-8')
        if 'components/REUSABLE_COMPONENT_OWNERSHIP.md' not in source:
            errors.append(f'{relative}: reusable component ownership registry is not registered')

    integration_tabs_path = root / 'app' / 'templates' / 'components' / 'integration_workspace_tabs.html'
    integration_tabs = integration_tabs_path.read_text(encoding='utf-8')
    if 'components/framed_workspace_tabs.html' not in integration_tabs:
        errors.append('integration workspace tabs must import canonical framed workspace tabs')
    if 'components/operational_section_card.html' not in integration_tabs:
        errors.append('integration workspace tabs must import canonical operational section shell')
    if 'operational_section_card.shell_classes()' not in integration_tabs:
        errors.append('integration workspace tabs must delegate outer shell geometry to operational_section_card')
    if 'framed_workspace_tabs.render(' not in integration_tabs:
        errors.append('integration workspace tabs must delegate tab geometry to framed_workspace_tabs.render()')
    for forbidden in (
        'role="tablist"',
        '<button type="button"',
        'rounded-t-xl border px-4 py-2.5 text-sm font-semibold',
    ):
        if forbidden in integration_tabs:
            errors.append(f'integration workspace tabs duplicates framed tab ownership: {forbidden}')

    return errors


def validate(root: Path, baseline_path: Path) -> list[str]:
    payload = json.loads(baseline_path.read_text(encoding='utf-8'))
    baseline = payload.get('files', {})
    current = scan(root)
    errors: list[str] = []
    environment = Environment(autoescape=select_autoescape(default=True, default_for_string=True))
    errors.extend(_validate_component_ownership(root))

    for path in sorted(set(current) | set(baseline)):
        current_metrics = current.get(path, {metric: 0 for metric in _METRICS})
        baseline_metrics = baseline.get(path, {metric: 0 for metric in _METRICS})
        for metric in _METRICS:
            value = int(current_metrics.get(metric, 0))
            allowed = int(baseline_metrics.get(metric, 0))
            if value > allowed:
                errors.append(f'{path}: {metric} {value} exceeds debt ceiling {allowed}')
            elif value < allowed:
                errors.append(
                    f'{path}: {metric} debt fell from {allowed} to {value}; update the baseline in the same change'
                )

    for path in sorted((root / 'app' / 'templates').rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        relative = path.relative_to(root).as_posix()
        try:
            environment.parse(source)
        except TemplateSyntaxError as exc:
            errors.append(f'{relative}:{exc.lineno}: invalid Jinja template: {exc.message}')
        if re.search(r'<style\b', source, re.IGNORECASE):
            errors.append(f'{relative}: template-local <style> blocks are forbidden')
        if 'style=' in source and relative not in _APPROVED_INLINE_STYLE_COMPONENTS:
            errors.append(f'{relative}: inline style must be represented by a shared component or static utility class')

    progress_component = root / 'app' / 'templates' / 'components' / 'progress_bar.html'
    if not progress_component.exists():
        errors.append('shared progress component is missing')

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Prevent template-local UI debt from expanding.')
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument(
        '--baseline',
        type=Path,
        default=Path('docs/architecture/ui-inline-debt-baseline.json'),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline

    try:
        errors = validate(root, baseline)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    totals = {metric: 0 for metric in _METRICS}
    files = scan(root)
    for metrics in files.values():
        for metric in _METRICS:
            totals[metric] += metrics[metric]
    print(
        'KAORI UI inline debt is bounded across '
        f'{len(files)} templates: {totals["inline_styles"]} styles, '
        f'{totals["inline_scripts"]} scripts, '
        f'{totals["inline_event_handlers"]} event handlers.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
