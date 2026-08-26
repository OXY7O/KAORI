#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    tabular = read('app/reports/export/tabular.py')
    csv_standard = read('app/reports/export/csv/standard.py')
    csv_renderer = read('app/reports/export/csv/renderer.py')
    inventory_common = read('app/reports/export/inventory_common.py')
    xlsx_standard = read('app/reports/export/xlsx/standard.py')
    xlsx_schema = read('app/reports/export/xlsx/schema.py')
    xlsx_builder = read('app/reports/export/xlsx/builder.py')
    xlsx_overview = read('app/reports/export/xlsx/overview.py')
    xlsx_style = read('app/reports/export/xlsx/style.py')
    analytics_schema = read('app/reports/export/xlsx/analytics_schema.py')
    analytics_profiles = read('app/reports/export/xlsx/analytics_profiles.py')
    analytics_builder = read('app/reports/export/xlsx/analytics_builder.py')
    analytics_overview = read('app/reports/export/xlsx/analytics_overview.py')
    analytics_document_builder = read('app/reports/export/html_pdf/builder.py')
    xlsx_renderer = read('app/reports/export/xlsx/renderer.py')
    reporting_doc = read('docs/reports/kaori-reporting-standard-v1.md')
    tabular_doc = read('docs/reports/kaori-tabular-export-standard-v3.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "TABULAR_EXPORT_STANDARD: Final = 'kaori-tabular-export-v3.0'" in tabular,
        'tabular v3 standard is missing',
        errors,
    )
    require("CSV_STANDARD: Final = 'kaori-reporting-csv-v3.0'" in csv_standard, 'CSV v3 standard is missing', errors)
    require(
        "CSV_INTERCHANGE_PROFILE: Final = 'portable-tabular-v1'" in csv_standard,
        'CSV interoperability profile is missing',
        errors,
    )
    require(
        "CSV_CONTENT_TYPE: Final = 'text/csv; charset=utf-8'" in csv_standard,
        'CSV content type contract is missing',
        errors,
    )
    require(
        "XLSX_REPORTING_STANDARD: Final = 'kaori-reporting-xlsx-v2.0'" in xlsx_schema,
        'global XLSX reporting standard is missing',
        errors,
    )
    require(
        "INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v4.0'" in xlsx_schema,
        'Inventory XLSX v4 standard is missing',
        errors,
    )
    require(
        "ANALYTICS_WORKBOOK_STANDARD: Final = 'kaori-analytics-xlsx-v1.0'" in analytics_schema,
        'Analytics XLSX v1 standard is missing',
        errors,
    )
    require(
        'ANALYTICS_WORKBOOK_PROFILES' in analytics_profiles and 'ANALYTICS_XLSX_REPORT_TYPES' in analytics_profiles,
        'Analytics XLSX category profile registry is missing',
        errors,
    )
    require(
        'build_analytics_workbook' in analytics_builder
        and 'validate_analytics_xlsx_artifact' in analytics_builder
        and 'validate_analytics_xlsx_artifact(output_path)' in analytics_builder,
        'Analytics XLSX builder/runtime validation contract is incomplete',
        errors,
    )
    require(
        all(label in analytics_overview for label in ('Executive Snapshot', 'Executive Readout', 'Primary Visual', 'Supporting Data')),
        'Analytics XLSX Overview hierarchy is incomplete',
        errors,
    )
    require(
        'BarChart' in analytics_overview
        and 'LineChart' in analytics_overview
        and "chart.visual_type == 'composition_bar'" in analytics_overview
        and "primary_visual='composition_bar'" in analytics_profiles,
        'Analytics XLSX semantic chart renderers are incomplete',
        errors,
    )
    require(
        "primary_visual='comparison_bar'" in analytics_profiles
        and "title='Current vs Projected Resource Posture'" in analytics_profiles
        and "chart.visual_type == 'comparison_bar'" in analytics_overview,
        'Analytics Overview must use resource-level Current vs Projected forecast semantics',
        errors,
    )
    require(
        all(
            binding in analytics_document_builder
            for binding in (
                "'resource_posture': ('resource_snapshot',)",
                "'trend_forecast': ('forecast_snapshot',)",
                "'alerts_anomalies': ('alert_detail', 'alerts_snapshot')",
            )
        )
        and "status_label, status_tone = 'No Evidence', 'warning'" in analytics_document_builder,
        'Analytics CSV evidence sections are not bound to committed overview payloads',
        errors,
    )
    require(
        'def render_report_xlsx(' in xlsx_renderer and 'REPORT_FAMILY_ANALYTICS' in xlsx_renderer and 'collect_report_payload' in xlsx_renderer,
        'family-aware XLSX renderer does not route Analytics through the canonical collector',
        errors,
    )
    require(
        "'format_standard'" in tabular and "'tabular_standard'" in tabular and "'interchange_profile'" in tabular,
        'shared metadata contract is incomplete',
        errors,
    )
    require('json.dumps' in tabular, 'nested CSV values must use deterministic JSON', errors)
    require('protect_spreadsheet_formula' in tabular, 'formula-injection control must be shared', errors)

    require('build_inventory_export_dataset' in inventory_common, 'shared Inventory dataset builder is missing', errors)
    require('InventoryExportDataset' in inventory_common, 'shared Inventory dataset model is missing', errors)
    require('build_inventory_export_dataset' in csv_renderer, 'Inventory CSV must use shared dataset builder', errors)
    require('build_inventory_export_dataset' in xlsx_builder, 'Inventory XLSX must use shared dataset builder', errors)
    require('get_inventory_rows(' not in csv_renderer, 'Inventory CSV must not normalize rows independently', errors)
    require(
        'get_inventory_workbook_profile(' not in csv_renderer,
        'Inventory CSV must not resolve profiles independently',
        errors,
    )

    require('build_inventory_overview_sheet' in xlsx_builder, 'Overview sheet builder is not wired', errors)
    require(
        'validate_inventory_xlsx_artifact' in xlsx_builder
        and 'validate_inventory_xlsx_artifact(output_path)' in xlsx_builder,
        'XLSX runtime artifact validation gate is missing',
        errors,
    )
    require('INVENTORY_DATA_SHEET' in xlsx_builder, 'Inventory sheet contract is missing', errors)
    require('INVENTORY_METADATA_SHEET' in xlsx_builder, 'Metadata sheet contract is missing', errors)
    require('INVENTORY_DICTIONARY_SHEET' in xlsx_builder, 'Field Dictionary sheet contract is missing', errors)
    require(
        'Workbook Navigation' in xlsx_overview and 'sheet.parent.sheetnames' in xlsx_overview,
        'Overview workbook navigation is missing',
        errors,
    )
    require(
        all(
            label in xlsx_overview
            for label in ('Executive Snapshot', 'Executive Readout', 'Primary Visual', 'Supporting Data')
        ),
        'Overview executive hierarchy is incomplete',
        errors,
    )
    require(
        'HEADER_ROW = 5' in xlsx_builder and 'DATA_START_ROW = 6' in xlsx_builder,
        'canonical workbook row contract is missing',
        errors,
    )
    require('_inventory_context_line' in xlsx_builder, 'workbook context strip is missing', errors)
    require(
        'print_title_rows' in xlsx_builder and 'fitToWidth' in xlsx_style,
        'print-ready workbook settings are missing',
        errors,
    )
    require('freeze_panes:' not in xlsx_standard, 'legacy hard-coded freeze panes remain in profiles', errors)
    require('status_columns' not in xlsx_standard, 'legacy profile-level status columns remain', errors)
    require('semantic_type' in xlsx_schema, 'column-level semantic roles are missing', errors)
    require(
        'overview_metrics: tuple[InventoryOverviewMetric, ...]' in xlsx_schema
        and 'overview_chart: InventoryOverviewChart' in xlsx_schema,
        'every XLSX profile must own Overview metrics and a chart contract',
        errors,
    )
    require(
        "visual_type: Literal['ranked_bar', 'doughnut']" in xlsx_schema
        and "aggregation: Literal['count', 'value'] = 'count'" in xlsx_schema,
        'XLSX Overview visual semantics contract is missing',
        errors,
    )
    require(
        all(
            token in xlsx_schema
            for token in (
                'source_key',
                'scale_divisor',
                'ratio_numerator_key',
                'ratio_denominator_key',
                'unit',
            )
        ),
        'profile-owned public transforms are missing',
        errors,
    )
    require('normalize_inventory_row' in inventory_common, 'shared public row normalization is missing', errors)
    require(
        'build_inventory_overview_sheet' in xlsx_builder
        and 'BarChart' in xlsx_overview
        and 'DoughnutChart' in xlsx_overview
        and 'DataLabelList' in xlsx_overview
        and 'visual.varyColors = False' in xlsx_overview,
        'XLSX Overview/chart contract is missing',
        errors,
    )
    require(
        "'negative_condition'" in xlsx_builder,
        'negative Kubernetes conditions do not have dedicated semantic formatting',
        errors,
    )
    require(
        'len(profile.identity_columns)' in xlsx_builder, 'frozen columns must be derived from identity columns', errors
    )
    require(
        'style_title' in xlsx_builder and 'style_header' in xlsx_builder,
        'workbook must use shared style primitives',
        errors,
    )

    require(
        "'record_reference'" in csv_standard and "'field_order'" in csv_standard and "'unit'" in csv_standard,
        'CSV stable record/unit fields are missing',
        errors,
    )
    require('build_analytics_csv_records' in csv_renderer, 'Analytics CSV record builder is missing', errors)
    require('_table_record_reference' in csv_renderer, 'Analytics table records need stable references', errors)
    require("'no_data'" in csv_renderer, 'Inventory CSV must preserve metadata for empty datasets', errors)

    require('KAORI Tabular Export Standard v3' in tabular_doc, 'tabular v3 documentation title is missing', errors)
    require('kaori-reporting-csv-v3.0' in tabular_doc, 'CSV v3 documentation is missing', errors)
    require('kaori-reporting-xlsx-v2.0' in tabular_doc, 'global XLSX v2 documentation is missing', errors)
    require('kaori-inventory-xlsx-v4.0' in tabular_doc, 'Inventory XLSX v4 documentation is missing', errors)
    require(
        'kaori-tabular-export-standard-v3.md' in reporting_doc,
        'reporting standard does not reference tabular v3',
        errors,
    )
    require(
        'verify_tabular_export_standard.py' in quality_gate,
        'tabular verifier is not registered in quality gate',
        errors,
    )

    for path in (
        'app/reports/export/tabular.py',
        'app/reports/export/csv/standard.py',
        'app/reports/export/csv/renderer.py',
        'app/reports/export/inventory_common.py',
        'app/reports/export/xlsx/standard.py',
        'app/reports/export/xlsx/schema.py',
        'app/reports/export/xlsx/style.py',
        'app/reports/export/xlsx/builder.py',
        'app/reports/export/xlsx/overview.py',
        'app/reports/export/xlsx/analytics_schema.py',
        'app/reports/export/xlsx/analytics_profiles.py',
        'app/reports/export/xlsx/analytics_builder.py',
        'app/reports/export/xlsx/analytics_overview.py',
        'app/reports/export/xlsx/renderer.py',
    ):
        try:
            ast.parse(read(path), filename=path)
        except SyntaxError as exc:
            errors.append(f'{path}: {exc}')

    if re.search(r"join\([^\n]*'; '", csv_renderer):
        errors.append('ad-hoc semicolon serialization remains in CSV renderer')

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI tabular export audit passed: CSV v3 and global XLSX v2 cover Inventory XLSX v4 and '
        'Analytics XLSX v1 with shared metadata/security contracts, category-owned Overview semantics, and runtime validation.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
