#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / 'app' / 'reports' / 'catalog.py'
CATALOG_DEFINITION_PATH = ROOT / 'app' / 'definitions' / 'catalogs' / 'reports' / 'catalog.yaml'
ARTIFACT_PATH = ROOT / 'app' / 'reports' / 'export' / 'artifacts.py'
REFERENCE_PATH = ROOT / 'app' / 'reports' / 'reference.py'
ANALYTICS_PUBLICATION_PATH = ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'analytics_publication_standard.py'
ANALYTICS_CSS_ROOT = ROOT / 'app' / 'static' / 'reports' / 'pdf'
CSV_STANDARD_PATH = ROOT / 'app' / 'reports' / 'export' / 'csv' / 'standard.py'
XLSX_SCHEMA_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'schema.py'
XLSX_BUILDER_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'builder.py'
XLSX_OVERVIEW_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'overview.py'
ANALYTICS_XLSX_PROFILE_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'analytics_profiles.py'
ANALYTICS_XLSX_SCHEMA_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'analytics_schema.py'
ANALYTICS_XLSX_BUILDER_PATH = ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'analytics_builder.py'
ANALYTICS_COLLECTOR_PATH = ROOT / 'app' / 'reports' / 'export' / 'html_pdf' / 'collectors.py'
INVENTORY_PROFILE_PATHS = (
    ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'profiles_kubernetes.py',
    ROOT / 'app' / 'reports' / 'export' / 'xlsx' / 'profiles_infrastructure.py',
)
MODEL_PATH = ROOT / 'app' / 'models' / 'report.py'
STANDARD_PATH = ROOT / 'docs' / 'reports' / 'kaori-reporting-standard-v1.md'
AUDIT_PATH = ROOT / 'docs' / 'reviews' / 'report-generation-audit-2026-08-03.md'

ANALYTICS_FORMATS = {'pdf', 'xlsx', 'csv'}
INVENTORY_FORMATS = {'xlsx', 'csv'}
SUPPORTED_SCOPE_ASSET_TYPES = {'kubernetes_cluster', 'object_storage_system'}
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


def _name(node: ast.AST | None) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _catalog_specs() -> dict[str, dict[str, object]]:
    document = yaml.safe_load(_read(CATALOG_DEFINITION_PATH))
    specs: dict[str, dict[str, object]] = {}
    for item in document.get('report_types') or []:
        report_type = str(item.get('value') or '').strip()
        if not report_type:
            continue
        specs[report_type] = {
            'family': str(item.get('family') or ''),
            'default_format': str(item.get('default_format') or ''),
            'allowed_formats': tuple(str(value) for value in item.get('allowed_formats') or []),
            'requires_cluster': bool(item.get('requires_cluster', True)),
            'domain': str(item.get('domain') or 'kubernetes'),
            'scope_asset_type': str(item.get('scope_asset_type') or 'kubernetes_cluster'),
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


def _function_uses_attribute(path: Path, function_name: str, attribute_name: str) -> bool:
    tree = _parse(path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return any(isinstance(child, ast.Attribute) and child.attr == attribute_name for child in ast.walk(node))
    return False


def _check_catalog(errors: list[str]) -> tuple[set[str], set[str]]:
    specs = _catalog_specs()
    if not specs:
        errors.append('Definition Registry report catalog contains no report type entries.')
        return set(), set()

    analytics = {key for key, value in specs.items() if value['family'] == 'analytics'}
    inventory = {key for key, value in specs.items() if value['family'] == 'inventory'}
    for report_type, spec in specs.items():
        family = spec['family']
        allowed = set(spec['allowed_formats'])
        default = spec['default_format']
        scope_asset_type = str(spec['scope_asset_type'])

        if scope_asset_type not in SUPPORTED_SCOPE_ASSET_TYPES:
            errors.append(f'{report_type} uses unsupported report scope asset type {scope_asset_type!r}.')
        if scope_asset_type == 'kubernetes_cluster' and spec['requires_cluster'] is not True:
            errors.append(f'{report_type} is Kubernetes-scoped but does not require one selected cluster.')
        if scope_asset_type == 'object_storage_system' and spec['requires_cluster'] is not False:
            errors.append(f'{report_type} is Object Storage-scoped but still requires a Kubernetes cluster.')

        if family == 'analytics':
            if allowed != ANALYTICS_FORMATS or default != 'pdf':
                errors.append(f'{report_type} does not use the Analytics PDF/XLSX/CSV contract.')
        elif family == 'inventory':
            if allowed != INVENTORY_FORMATS or default != 'xlsx':
                errors.append(f'{report_type} does not use the Inventory XLSX/CSV contract.')
        else:
            errors.append(f'{report_type} has an unknown report family: {family!r}.')

    catalog_source = _read(CATALOG_PATH)
    if "load_definition_document('reports/catalog.yaml'" not in catalog_source:
        errors.append('Runtime report catalog does not load reports/catalog.yaml from the Definition Registry.')
    if 'scope_asset_type' not in catalog_source:
        errors.append('Runtime report catalog does not expose generic asset scope metadata.')
    return analytics, inventory


def _check_renderer_coverage(
    errors: list[str],
    analytics: set[str],
    inventory: set[str],
) -> None:
    analytics_collectors = _dictionary_string_keys(ANALYTICS_COLLECTOR_PATH, '_PAYLOAD_COLLECTORS')
    analytics_xlsx_profiles = _dictionary_string_keys(ANALYTICS_XLSX_PROFILE_PATH, 'ANALYTICS_WORKBOOK_PROFILES')
    inventory_profiles = set().union(
        _dictionary_string_keys(INVENTORY_PROFILE_PATHS[0], 'KUBERNETES_INVENTORY_WORKBOOK_PROFILES'),
        _dictionary_string_keys(INVENTORY_PROFILE_PATHS[1], 'INFRASTRUCTURE_INVENTORY_WORKBOOK_PROFILES'),
    )
    if analytics_collectors != analytics:
        errors.append(
            'Analytics collector coverage differs from the catalog: '
            f'missing={sorted(analytics - analytics_collectors)}, '
            f'extra={sorted(analytics_collectors - analytics)}.'
        )
    if analytics_xlsx_profiles != analytics:
        errors.append(
            'Analytics XLSX profile coverage differs from the catalog: '
            f'missing={sorted(analytics - analytics_xlsx_profiles)}, '
            f'extra={sorted(analytics_xlsx_profiles - analytics)}.'
        )
    if inventory_profiles != inventory:
        errors.append(
            'Inventory workbook/CSV profile coverage differs from the catalog: '
            f'missing={sorted(inventory - inventory_profiles)}, '
            f'extra={sorted(inventory_profiles - inventory)}.'
        )

    analytics_schema = _read(ANALYTICS_XLSX_SCHEMA_PATH)
    analytics_builder = _read(ANALYTICS_XLSX_BUILDER_PATH)
    if "ANALYTICS_WORKBOOK_STANDARD: Final = 'kaori-analytics-xlsx-v1.0'" not in analytics_schema:
        errors.append('Analytics XLSX workbook standard is missing or stale.')
    if 'validate_analytics_xlsx_artifact(output_path)' not in analytics_builder:
        errors.append('Analytics XLSX runtime artifact validation gate is missing.')

    artifact_source = _read(ARTIFACT_PATH)
    expected_mappings = (
        'FORMAT_PDF: render_weasyprint_pdf',
        'FORMAT_XLSX: render_report_xlsx',
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


def _check_public_reference_coverage(errors: list[str]) -> None:
    report_types = set(_catalog_specs())
    reference_codes = _dictionary_string_keys(REFERENCE_PATH, 'REPORT_TYPE_CODES')
    if reference_codes != report_types:
        errors.append(
            'Public report reference code coverage differs from the Definition Registry: '
            f'missing={sorted(report_types - reference_codes)}, '
            f'extra={sorted(reference_codes - report_types)}.'
        )


def _check_cross_format_standards(errors: list[str]) -> None:
    csv_source = _read(CSV_STANDARD_PATH)
    xlsx_schema = _read(XLSX_SCHEMA_PATH)
    xlsx_builder = _read(XLSX_BUILDER_PATH)
    xlsx_overview = _read(XLSX_OVERVIEW_PATH)
    for token in (
        "CSV_STANDARD: Final = 'kaori-reporting-csv-v3.0'",
        "CSV_INTERCHANGE_PROFILE: Final = 'portable-tabular-v1'",
        "CSV_CONTENT_TYPE: Final = 'text/csv; charset=utf-8'",
        "CSV_ENCODING: Final = 'utf-8-sig'",
        "CSV_LINE_TERMINATOR: Final = '\\n'",
        'protect_spreadsheet_formula',
    ):
        if token not in csv_source:
            errors.append(f'CSV standard is missing required contract token: {token}.')

    for token in (
        "XLSX_REPORTING_STANDARD: Final = 'kaori-reporting-xlsx-v2.0'",
        "INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v4.0'",
        "INVENTORY_OVERVIEW_SHEET: Final = 'Overview'",
        "INVENTORY_DATA_SHEET: Final = 'Inventory'",
        "INVENTORY_METADATA_SHEET: Final = 'Metadata'",
        "INVENTORY_DICTIONARY_SHEET: Final = 'Field Dictionary'",
    ):
        if token not in xlsx_schema:
            errors.append(f'XLSX standard is missing required contract token: {token}.')

    for token in (
        'build_inventory_export_dataset(',
        'build_inventory_overview_sheet(',
        'style_title(',
        'style_header(',
        'configure_sheet_page(',
    ):
        if token not in xlsx_builder:
            errors.append(f'Inventory XLSX builder is missing required reusable contract token: {token}.')

    for token in (
        'Executive Snapshot',
        'Executive Readout',
        'Primary Visual',
        'Supporting Data',
        'Workbook Navigation',
        'BarChart',
        'DoughnutChart',
        'DataLabelList',
        'visual.varyColors = False',
    ):
        if token not in xlsx_overview:
            errors.append(f'Inventory XLSX Overview is missing required contract token: {token}.')

    if not _function_uses_attribute(
        XLSX_OVERVIEW_PATH,
        '_write_overview_navigation',
        'sheetnames',
    ):
        errors.append('Inventory XLSX Overview navigation must derive targets from workbook sheet names.')

    mapped_templates = _dictionary_string_keys(ANALYTICS_PUBLICATION_PATH, 'ANALYTICS_TEMPLATE_STYLESHEETS')
    expected_templates = {
        'reports/pdf/analytics_overview.html',
        'reports/pdf/resource_utilization.html',
        'reports/pdf/capacity_analysis.html',
        'reports/pdf/storage_analysis.html',
        'reports/pdf/workload_analysis.html',
        'reports/pdf/forecast_analysis.html',
        'reports/pdf/top_consumers_analysis.html',
        'reports/pdf/alerts_anomalies.html',
        'reports/pdf/object_storage_analysis.html',
        'reports/pdf/analytics_unavailable.html',
    }
    if mapped_templates != expected_templates:
        errors.append(
            'Analytics PDF publication template coverage drifted from the canonical family: '
            f'missing={sorted(expected_templates - mapped_templates)}, '
            f'extra={sorted(mapped_templates - expected_templates)}.'
        )

    for template_name in mapped_templates:
        template_path = ROOT / 'app' / 'templates' / template_name
        if not template_path.exists():
            errors.append(f'Analytics publication template is missing: {template_name}.')
            continue
        source = _read(template_path)
        if 'kaori-analytics-publication' not in source or 'kaori-reporting-v3' not in source:
            errors.append(f'{template_name} does not opt into the canonical Analytics publication classes.')
        if 'components/analytics_publication.html' not in source:
            errors.append(f'{template_name} does not reuse the canonical Analytics publication component.')

    # Report-specific styles may specialize geometry, but generic table typography belongs to shared publication CSS.
    geometry_only_css = (
        'alerts_anomalies.css',
        'capacity_analysis.css',
        'forecast_analysis.css',
        'resource_utilization.css',
        'storage_analysis.css',
        'top_consumers_analysis.css',
        'workload_analysis.css',
        'object_storage_analysis.css',
    )
    for filename in geometry_only_css:
        path = ANALYTICS_CSS_ROOT / filename
        source = _read(path)
        for line in source.splitlines():
            if '.report-table' in line and 'font-size:' in line and 'var(--analytics-type-' not in line:
                errors.append(
                    f'{path.relative_to(ROOT)} hard-codes generic report-table typography; '
                    'use the Analytics Overview shared type tokens instead.'
                )

    standard_source = _read(STANDARD_PATH).lower()
    required_phrases = (
        'object storage',
        'selected-asset boundary',
        'xlsx',
        'legacy `.xls` is not supported',
        'machine-readable exchange artifact',
    )
    for phrase in required_phrases:
        if phrase.lower() not in standard_source:
            errors.append(f'{STANDARD_PATH.relative_to(ROOT)} is missing cross-format standard language: {phrase!r}.')


def _check_asset_scope_and_legacy(errors: list[str]) -> None:
    model_source = _read(MODEL_PATH)
    if "default='pdf'" in model_source:
        errors.append('A universal PDF model default still exists; output must be family-specific.')
    for field in ('scope_asset_type', 'scope_asset_id', 'scope_asset_label_snapshot'):
        if field not in model_source:
            errors.append(f'Report persistence is missing generic scope field {field}.')

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

    required_scope_files = (
        ROOT / 'app' / 'reports' / 'generate' / 'service.py',
        ROOT / 'app' / 'reports' / 'schedules' / 'service.py',
        ROOT / 'app' / 'reports' / 'jobs' / 'contract.py',
        ROOT / 'app' / 'reports' / 'storage' / 'naming.py',
    )
    for path in required_scope_files:
        source = _read(path)
        if 'scope_asset' not in source and 'resolve_report_scope' not in source:
            errors.append(f'{path.relative_to(ROOT)} has no visible generic report asset-scope contract.')


def _check_documentation(errors: list[str]) -> None:
    for path in (STANDARD_PATH, AUDIT_PATH):
        if not path.exists():
            errors.append(f'Required report documentation is missing: {path.relative_to(ROOT)}.')
            continue
        source = _read(path).lower()
        for phrase in ('analytics', 'inventory', 'csv'):
            if phrase not in source:
                errors.append(f'{path.relative_to(ROOT)} does not document {phrase!r}.')


def main() -> int:
    errors: list[str] = []
    analytics, inventory = _check_catalog(errors)
    _check_renderer_coverage(errors, analytics, inventory)
    _check_public_reference_coverage(errors)
    _check_cross_format_standards(errors)
    _check_asset_scope_and_legacy(errors)
    _check_documentation(errors)

    if errors:
        print('FAIL — KAORI Report Generation Contract')
        print()
        print('Contract Errors')
        for error in errors:
            print(f'  FAIL — {error}')
        print()
        print('Summary')
        print(f'  {len(errors)} failed')
        return 1

    print('PASS — KAORI Report Generation Contract')
    print()
    print('Formats & Rendering')
    print('  PASS — Analytics supports canonical PDF, XLSX, and CSV artifacts.')
    print('  PASS — Inventory supports canonical XLSX and CSV artifacts.')
    print()
    print('Registry & References')
    print('  PASS — Report profiles, collectors, and public references match the Definition Registry.')
    print()
    print('Workbook Contracts')
    print('  PASS — Inventory and Analytics workbook contracts are structurally valid.')
    print('  PASS — Inventory workbook navigation derives targets from workbook sheet names.')
    print()
    print('Scope & Legacy Safety')
    print('  PASS — Generic infrastructure asset scope is preserved across report formats.')
    print('  PASS — Retired report-generation paths are absent.')
    print()
    print('Summary')
    print('  7 checks passed · 0 failed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
