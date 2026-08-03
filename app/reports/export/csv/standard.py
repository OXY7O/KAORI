from __future__ import annotations

CSV_STANDARD = 'KAORI Reporting CSV v1'
CSV_ENCODING = 'utf-8-sig'
CSV_DELIMITER = ','
CSV_LINE_TERMINATOR = '\n'

COMMON_METADATA_HEADERS = (
    'report_standard',
    'report_id',
    'report_name',
    'report_type',
    'report_family',
    'cluster',
    'namespace',
    'period',
    'data_cutoff',
)

ANALYTICS_HEADERS = (
    *COMMON_METADATA_HEADERS,
    'section_number',
    'section',
    'record_type',
    'record_number',
    'field',
    'value',
    'note',
    'status',
    'tone',
)


def protect_spreadsheet_formula(value: object) -> str:
    """Prevent spreadsheet formula execution when CSV is opened by office tools."""

    text = '' if value is None else str(value)
    stripped = text.lstrip()
    if stripped.startswith(('=', '+', '-', '@')):
        return f"'{text}"
    return text
