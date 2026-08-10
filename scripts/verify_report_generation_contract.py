#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'app' / 'reports' / 'catalog.py'
ARTIFACT_PATH = ROOT / 'app' / 'reports' / 'export' / 'artifacts.py'
ANALYTICS_COLLECTOR_PATH = ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'collectors.py'
INVENTORY_PROFILE_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'standard.py'
MODEL_PATH = ROOT / 'app' / 'models' / 'report.py'
STANDARD_PATH = ROOT / 'docs' / 'reports' / 'kaori-reporting-standard-v1.md'
AUDIT_PATH = ROOT / 'docs' / 'reviews' / 'report-generation-audit-2026-08-03.md'

ANALYTICS_FORMATS = {'pdf', 'csv'}
INVENTORY_FORMATS = {'xlsx', 'csv'}
FORBIDDEN_TOKENS = (
    'generate_report_pdf',
    'download_report_pdf',
    'generate_pdf_for_report',
    'topology_inventory',
    'tls_certificate_health',
    'all-clusters',
)


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _parse(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _name(node: ast.AST | None) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _catalog_specs() -> dict[str, dict[str, object]]:
    specs: dict[str, dict[str, object]] = {}
    for node in ast.walk(_parse(CATALOG_PATH)):
        if not isinstance(node, ast.Call) or _name(node.func) != 'ReportTypeSpec':
            continue
        values = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
        report_type = _literal_string(values.get('value'))
        if not report_type:
            continue
        specs[report_type] = {
            'family': _name(values.get('family')),
            'default_format': _name(values.get('default_format')),
            'allowed_formats': _name(values.get('allowed_formats')),
            'requires_cluster': (
                values.get('requires_cluster').value
                if isinstance(values.get('requires_cluster'), ast.Constant)
                else True
            ),
        }
    return specs


def _dictionary_string_keys(path: Path, variable_name: str) -> set[str]:
    tree = _parse(path)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
        value = node.value
        if _name(target) != variable_name or not isinstance(value, ast.Dict):
            continue
        return {key.value for key in value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    return set()


def _check_catalog(errors: list[str]) -> tuple[set[str], set[str]]:
    specs = _catalog_specs()
    if not specs:
        errors.append('Central report catalog contains no ReportTypeSpec entries.')
        return set(), set()

    analytics = {key for key, value in specs.items() if value['family'] == 'REPORT_FAMILY_ANALYTICS'}
    inventory = {key for key, value in specs.items() if value['family'] == 'REPORT_FAMILY_INVENTORY'}
    for report_type, spec in specs.items():
        if spec['requires_cluster'] is not True:
            errors.append(f'{report_type} does not require a selected cluster.')
        family = spec['family']
        allowed = spec['allowed_formats']
        default = spec['default_format']
        if family == 'REPORT_FAMILY_ANALYTICS':
            if allowed != '_ANALYTICS_FORMATS' or default != 'FORMAT_PDF':
                errors.append(f'{report_type} does not use the Analytics PDF/CSV contract.')
        elif family == 'REPORT_FAMILY_INVENTORY':
            if allowed != '_INVENTORY_FORMATS' or default != 'FORMAT_XLSX':
                errors.append(f'{report_type} does not use the Inventory XLSX/CSV contract.')
        else:
            errors.append(f'{report_type} has an unknown report family: {family!r}.')

    catalog_source = _read(CATALOG_PATH)
    if '_ANALYTICS_FORMATS = (FORMAT_PDF, FORMAT_CSV)' not in catalog_source:
        errors.append('Analytics format tuple is not exactly PDF and CSV.')
    if '_INVENTORY_FORMATS = (FORMAT_XLSX, FORMAT_CSV)' not in catalog_source:
        errors.append('Inventory format tuple is not exactly XLSX and CSV.')
    return analytics, inventory


def _check_renderer_coverage(
    errors: list[str],
    analytics: set[str],
    inventory: set[str],
) -> None:
    analytics_collectors = _dictionary_string_keys(ANALYTICS_COLLECTOR_PATH, '_PAYLOAD_COLLECTORS')
    inventory_profiles = _dictionary_string_keys(INVENTORY_PROFILE_PATH, 'INVENTORY_WORKBOOK_PROFILES')
    if analytics_collectors != analytics:
        errors.append(
            'Analytics collector coverage differs from the catalog: '
            f'missing={sorted(analytics - analytics_collectors)}, '
            f'extra={sorted(analytics_collectors - analytics)}.'
        )
    if inventory_profiles != inventory:
        errors.append(
            'Inventory workbook/CSV profile coverage differs from the catalog: '
            f'missing={sorted(inventory - inventory_profiles)}, '
            f'extra={sorted(inventory_profiles - inventory)}.'
        )

    artifact_source = _read(ARTIFACT_PATH)
    expected_mappings = (
        'FORMAT_PDF: render_weasyprint_pdf',
        'FORMAT_XLSX: render_inventory_xlsx',
        'FORMAT_CSV: render_report_csv',
    )
    for mapping in expected_mappings:
        if mapping not in artifact_source:
            errors.append(f'Artifact registry is missing canonical mapping: {mapping}.')

    package_renderer_imports = (
        (
            ROOT / 'app' / 'reports' / 'export' / 'xlsx' / '__init__.py',
            'from app.reports.export.xlsx.renderer import render_inventory_xlsx\n',
            'XLSX',
        ),
        (
            ROOT / 'app' / 'reports' / 'export' / 'csv' / '__init__.py',
            'from app.reports.export.csv.renderer import render_report_csv\n',
            'CSV',
        ),
    )
    for package_init_path, eager_renderer_import, label in package_renderer_imports:
        if eager_renderer_import in _read(package_init_path):
            errors.append(
                f'The {label} package initializer eagerly imports its renderer; renderer '
                'modules must remain behind a lazy package boundary to prevent circular imports.'
            )


def _check_selected_cluster_and_legacy(errors: list[str]) -> None:
    model_source = _read(MODEL_PATH)
    if "default='pdf'" in model_source:
        errors.append('A universal PDF model default still exists; output must be family-specific.')

    active_roots = (
        ROOT / 'app' / 'reports',
        ROOT / 'app' / 'templates' / 'reports',
        ROOT / 'app' / 'static' / 'reports',
        ROOT / 'tests' / 'reports',
    )
    for root in active_roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            try:
                source = _read(path).lower()
            except UnicodeDecodeError:
                continue
            for token in FORBIDDEN_TOKENS:
                if token in source:
                    errors.append(f'{path.relative_to(ROOT)} contains forbidden legacy token {token!r}.')

    required_guard_files = (
        ROOT / 'app' / 'reports' / 'generate' / 'service.py',
        ROOT / 'app' / 'reports' / 'schedules' / 'service.py',
        ROOT / 'app' / 'reports' / 'export' / 'payloads' / 'common.py',
        ROOT / 'app' / 'reports' / 'storage' / 'naming.py',
    )
    for path in required_guard_files:
        source = _read(path)
        if (
            'selected cluster' not in source.lower()
            and 'require_selected_cluster' not in source
            and 'validate_report_contract' not in source
        ):
            errors.append(f'{path.relative_to(ROOT)} has no visible selected-cluster guard.')


def _check_documentation(errors: list[str]) -> None:
    for path in (STANDARD_PATH, AUDIT_PATH):
        if not path.exists():
            errors.append(f'Required report documentation is missing: {path.relative_to(ROOT)}.')
            continue
        source = _read(path).lower()
        for phrase in ('selected cluster', 'analytics', 'inventory', 'csv'):
            if phrase not in source:
                errors.append(f'{path.relative_to(ROOT)} does not document {phrase!r}.')


def main() -> int:
    errors: list[str] = []
    analytics, inventory = _check_catalog(errors)
    _check_renderer_coverage(errors, analytics, inventory)
    _check_selected_cluster_and_legacy(errors)
    _check_documentation(errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI report generation contract passed: Analytics supports PDF/CSV, Inventory supports '
        'XLSX/CSV, every report requires one selected cluster, renderer/profile coverage matches '
        'the central catalog, and legacy generation paths are absent.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
