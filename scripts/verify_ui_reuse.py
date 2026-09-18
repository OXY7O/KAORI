#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jinja2 import Environment, TemplateSyntaxError, select_autoescape

_METRICS = ('inline_styles', 'inline_scripts', 'inline_event_handlers')
_EVENT_HANDLER = re.compile(
    r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=',
    re.IGNORECASE,
)
_SCRIPT_TAG = re.compile(r'<script\b(?P<attrs>[^>]*)>', re.IGNORECASE | re.DOTALL)
_INERT_JSON_SCRIPT_TYPE = re.compile(
    r"""\btype\s*=\s*(?:"application/json"|'application/json'|application/json)(?=\s|$)""",
    re.IGNORECASE,
)
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


def _approved_prepaint_script_starts(relative: str, source: str) -> set[int]:
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

    for match in _SCRIPT_BLOCK.finditer(source):
        attrs = match.group('attrs').strip()
        marker_match = _PREPAINT_BOOTSTRAP_MARKER.search(attrs)
        marker = marker_match.group('marker') if marker_match else None
        if marker != expected_marker:
            continue
        if attrs != expected_attrs:
            continue
        if match.start() >= head_end or match.start() >= stylesheet:
            continue
        if _normalize_script_body(match.group('body')) != expected_body:
            continue
        approved.append(match.start())

    return set(approved) if len(approved) == 1 else set()


def _metrics(relative: str, source: str) -> dict[str, int]:
    return {
        'inline_styles': (
            0
            if relative in _APPROVED_INLINE_STYLE_COMPONENTS
            else len(re.findall(r'\bstyle\s*=', source, re.IGNORECASE))
        ),
        'inline_scripts': sum(
            1
            for match in _SCRIPT_TAG.finditer(source)
            if not re.search(r'\bsrc\s*=', match.group('attrs'), re.IGNORECASE)
            and not _INERT_JSON_SCRIPT_TYPE.search(match.group('attrs'))
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


def validate(root: Path, baseline_path: Path) -> list[str]:
    payload = json.loads(baseline_path.read_text(encoding='utf-8'))
    baseline = payload.get('files', {})
    current = scan(root)
    errors: list[str] = []
    environment = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

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
