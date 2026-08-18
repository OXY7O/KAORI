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
    xlsx_style = read('app/reports/export/xlsx/style.py')
    reporting_doc = read('docs/reports/kaori-reporting-standard-v1.md')
    tabular_doc = read('docs/reports/kaori-tabular-export-standard-v2.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        "TABULAR_EXPORT_STANDARD: Final = 'kaori-tabular-export-v2.0'" in tabular,
        'tabular v2 standard is missing',
        errors,
    )
    require("CSV_STANDARD: Final = 'kaori-reporting-csv-v2.0'" in csv_standard, 'CSV v2 standard is missing', errors)
    require(
        "INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v2.0'" in xlsx_schema,
        'XLSX v2 standard is missing',
        errors,
    )
    require(
        "'format_standard'" in tabular and "'tabular_standard'" in tabular,
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

    require('INVENTORY_DATA_SHEET' in xlsx_builder, 'Inventory sheet contract is missing', errors)
    require('INVENTORY_METADATA_SHEET' in xlsx_builder, 'Metadata sheet contract is missing', errors)
    require('INVENTORY_DICTIONARY_SHEET' in xlsx_builder, 'Field Dictionary sheet contract is missing', errors)
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
        "'record_reference'" in csv_standard and "'field_order'" in csv_standard,
        'CSV stable record fields are missing',
        errors,
    )
    require('build_analytics_csv_records' in csv_renderer, 'Analytics CSV record builder is missing', errors)
    require('_table_record_reference' in csv_renderer, 'Analytics table records need stable references', errors)
    require("'no_data'" in csv_renderer, 'Inventory CSV must preserve metadata for empty datasets', errors)

    require('KAORI Tabular Export Standard v2' in tabular_doc, 'tabular v2 documentation title is missing', errors)
    require('kaori-reporting-csv-v2.0' in tabular_doc, 'CSV v2 documentation is missing', errors)
    require('kaori-inventory-xlsx-v2.0' in tabular_doc, 'XLSX v2 documentation is missing', errors)
    require(
        'kaori-tabular-export-standard-v2.md' in reporting_doc,
        'reporting standard does not reference tabular v2',
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
        'KAORI tabular export audit passed: CSV v2 and Inventory XLSX v2 share '
        'metadata, dataset, identity, normalization, security, and schema contracts.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
