#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _active_text_files() -> list[Path]:
    candidates: list[Path] = []
    for root_name in ('app', 'tests', 'requirements', 'docs', 'scripts'):
        root = ROOT / root_name
        candidates.extend(path for path in root.rglob('*') if path.is_file())
    candidates.extend(
        path
        for path in (
            ROOT / '.env.example',
            ROOT / '.env.production.example',
            ROOT / 'Dockerfile',
            ROOT / 'README.md',
            ROOT / 'pyproject.toml',
        )
        if path.exists()
    )
    return candidates


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return ''


def main() -> int:
    export_root = ROOT / 'app' / 'reports' / 'export'
    removed_paths = (
        export_root / 'renderers',
        export_root / 'sections',
        export_root / 'helpers.py',
        export_root / 'styles.py',
    )
    errors: list[str] = []

    for path in removed_paths:
        if path.exists():
            errors.append(f'Legacy PDF path still exists: {path.relative_to(ROOT)}')

    forbidden_patterns = {
        'old package': re.compile(r'\b' + ('report' + 'lab') + r'\b', re.IGNORECASE),
        'runtime renderer selector': re.compile('REPORT_PDF_' + 'RENDERER', re.IGNORECASE),
        'old fallback setting': re.compile('REPORT_PDF_' + 'LEGACY_FALLBACK_ENABLED', re.IGNORECASE),
        'old renderer import': re.compile(re.escape('app.reports.export.' + 'renderers'), re.IGNORECASE),
        'old section import': re.compile(re.escape('app.reports.export.' + 'sections'), re.IGNORECASE),
        'old helper import': re.compile(re.escape('app.reports.export.' + 'helpers'), re.IGNORECASE),
        'old style import': re.compile(re.escape('app.reports.export.' + 'styles'), re.IGNORECASE),
    }

    for path in _active_text_files():
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        content = _read_text(path)
        for label, pattern in forbidden_patterns.items():
            if pattern.search(content):
                errors.append(f'{path.relative_to(ROOT)} still contains {label}.')

    requirements_input = _read_text(ROOT / 'requirements' / 'base.in')
    requirements_lock = _read_text(ROOT / 'requirements' / 'base.txt')
    for path, content in (
        ('requirements/base.in', requirements_input),
        ('requirements/base.txt', requirements_lock),
    ):
        if 'weasyprint==68.0' not in content:
            errors.append(f'{path} does not declare the canonical WeasyPrint runtime.')

    service_path = export_root / 'service.py'
    service_source = _read_text(service_path)
    try:
        service_tree = ast.parse(service_source, filename=str(service_path))
    except SyntaxError as exc:
        errors.append(f'{service_path.relative_to(ROOT)} cannot be parsed: {exc}')
    else:
        imports_canonical_renderer = any(
            isinstance(node, ast.ImportFrom)
            and node.module == 'app.reports.export.html_pdf.renderer'
            and any(alias.name == 'render_weasyprint_pdf' for alias in node.names)
            for node in ast.walk(service_tree)
        )
        if not imports_canonical_renderer:
            errors.append('Report export service does not import the canonical WeasyPrint renderer directly.')

        function_names = {
            node.name
            for node in service_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        forbidden_functions = {
            'render_' + 'report_pdf',
            'format_' + 'renderer_label',
            'render_' + 'reportlab_pdf',
        }
        for function_name in sorted(function_names & forbidden_functions):
            errors.append(f'Compatibility function still exists in report export service: {function_name}')

    collector_source = _read_text(export_root / 'html_pdf' / 'collectors.py')
    if 'app.reports.export.payloads.' not in collector_source:
        errors.append('Canonical PDF collector does not use the renderer-neutral payload package.')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI report PDF engine audit passed: one canonical WeasyPrint pipeline, '
        'no old engine dependency, selector, fallback, registry, or rendering source remains.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
