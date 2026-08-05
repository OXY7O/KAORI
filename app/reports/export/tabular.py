from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

TABULAR_EXPORT_STANDARD: Final = 'kaori-tabular-export-v2.0'
TABULAR_SCHEMA_VERSION: Final = '2.0'
_SPREADSHEET_NUMERIC_LITERAL = re.compile(
    r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
)

COMMON_EXPORT_METADATA_FIELDS: Final = (
    'format_standard',
    'tabular_standard',
    'schema_version',
    'document_reference',
    'report_name',
    'report_type',
    'report_type_label',
    'report_family',
    'classification',
    'generated_at',
    'generated_by',
    'selected_cluster',
    'selected_namespace',
    'reporting_period',
    'data_cutoff',
    'source_label',
)


@dataclass(frozen=True, slots=True)
class TabularExportMetadata:
    format_standard: str
    document_reference: str
    report_name: str
    report_type: str
    report_type_label: str
    report_family: str
    classification: str
    generated_at: datetime | str
    generated_by: str
    selected_cluster: str
    selected_namespace: str
    reporting_period: str
    data_cutoff: datetime | date | str | None
    source_label: str
    tabular_standard: str = TABULAR_EXPORT_STANDARD
    schema_version: str = TABULAR_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            'format_standard': self.format_standard,
            'tabular_standard': self.tabular_standard,
            'schema_version': self.schema_version,
            'document_reference': self.document_reference,
            'report_name': self.report_name,
            'report_type': self.report_type,
            'report_type_label': self.report_type_label,
            'report_family': self.report_family,
            'classification': self.classification,
            'generated_at': serialize_tabular_value(self.generated_at),
            'generated_by': self.generated_by,
            'selected_cluster': self.selected_cluster,
            'selected_namespace': self.selected_namespace,
            'reporting_period': self.reporting_period,
            'data_cutoff': serialize_tabular_value(self.data_cutoff),
            'source_label': self.source_label,
        }


def serialize_tabular_value(value: Any) -> str:
    """Return a deterministic CSV-safe scalar representation.

    Nested values use compact JSON rather than ad-hoc delimiter joining so a
    downstream reader can recover their structure without ambiguity.
    """

    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return json.dumps(list(value), ensure_ascii=False, separators=(',', ':'), default=str)
    if isinstance(value, set):
        return json.dumps(sorted(value, key=str), ensure_ascii=False, separators=(',', ':'), default=str)
    return str(value)


def tabular_value_type(value: Any) -> str:
    if value is None or value == '':
        return 'empty'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'integer'
    if isinstance(value, float):
        return 'number'
    if isinstance(value, datetime):
        return 'datetime'
    if isinstance(value, date):
        return 'date'
    if isinstance(value, Mapping):
        return 'object'
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return 'array'
    if isinstance(value, set):
        return 'array'
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r'[+-]?\d+', stripped):
            return 'integer'
        if re.fullmatch(r'[+-]?(?:\d+\.\d*|\d*\.\d+)', stripped):
            return 'number'
    return 'text'


def protect_spreadsheet_formula(value: object) -> str:
    """Prevent spreadsheet formula execution when CSV is opened by office tools."""

    text = '' if value is None else str(value)
    stripped = text.lstrip()
    if (
        stripped.startswith(('=', '+', '-', '@'))
        and _SPREADSHEET_NUMERIC_LITERAL.fullmatch(stripped) is None
    ):
        return f"'{text}"
    return text


def build_record_reference(
    row: Mapping[str, Any],
    identity_keys: Sequence[str],
    *,
    row_number: int,
    prefix: str = 'ROW',
) -> str:
    identity = [str(row.get(key) or '').strip() for key in identity_keys]
    populated = [item for item in identity if item and item.lower() != 'not available']
    if populated:
        return ' / '.join(populated)
    return f'{prefix}-{row_number:06d}'
