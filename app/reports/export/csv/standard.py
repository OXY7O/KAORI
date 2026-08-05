from __future__ import annotations

from typing import Final

from app.reports.export.tabular import (
    COMMON_EXPORT_METADATA_FIELDS,
    TABULAR_EXPORT_STANDARD,
    TABULAR_SCHEMA_VERSION,
    protect_spreadsheet_formula,
)

CSV_STANDARD: Final = 'kaori-reporting-csv-v2.0'
CSV_SCHEMA_VERSION: Final = TABULAR_SCHEMA_VERSION
CSV_TABULAR_STANDARD: Final = TABULAR_EXPORT_STANDARD
CSV_ENCODING: Final = 'utf-8-sig'
CSV_DELIMITER: Final = ','
CSV_LINE_TERMINATOR: Final = '\n'

COMMON_METADATA_HEADERS: Final = COMMON_EXPORT_METADATA_FIELDS

ANALYTICS_HEADERS: Final = (
    *COMMON_METADATA_HEADERS,
    'section_order',
    'section_key',
    'section_title',
    'dataset',
    'record_type',
    'record_reference',
    'record_order',
    'field_order',
    'field',
    'value',
    'value_type',
    'status',
    'tone',
    'note',
)

INVENTORY_CONTROL_HEADERS: Final = (
    'record_type',
    'record_reference',
    'row_number',
)

__all__ = [
    'ANALYTICS_HEADERS',
    'COMMON_METADATA_HEADERS',
    'CSV_DELIMITER',
    'CSV_ENCODING',
    'CSV_LINE_TERMINATOR',
    'CSV_SCHEMA_VERSION',
    'CSV_STANDARD',
    'CSV_TABULAR_STANDARD',
    'INVENTORY_CONTROL_HEADERS',
    'protect_spreadsheet_formula',
]
