from __future__ import annotations

import csv
from pathlib import Path

from app.reports.export.csv.renderer import _write_dict_rows
from app.reports.export.csv.standard import (
    ANALYTICS_HEADERS,
    COMMON_METADATA_HEADERS,
    CSV_ENCODING,
    CSV_STANDARD,
    protect_spreadsheet_formula,
)
from app.reports.export.xlsx.standard import INVENTORY_WORKBOOK_PROFILES


def test_csv_standard_has_stable_common_metadata_and_analytics_headers() -> None:
    assert CSV_STANDARD == 'KAORI Reporting CSV v1'
    assert ANALYTICS_HEADERS[: len(COMMON_METADATA_HEADERS)] == COMMON_METADATA_HEADERS
    assert ANALYTICS_HEADERS[len(COMMON_METADATA_HEADERS) :] == (
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


def test_csv_formula_controls_are_escaped() -> None:
    for value in ('=1+1', '+cmd', '-cmd', '@SUM(A1:A2)', '  =1+1'):
        assert protect_spreadsheet_formula(value).startswith("'")
    assert protect_spreadsheet_formula('normal') == 'normal'
    assert protect_spreadsheet_formula('42') == '42'


def test_csv_writer_uses_utf8_bom_lf_and_stable_header_order(tmp_path: Path) -> None:
    output = tmp_path / 'report.csv'
    headers = ('report_standard', 'cluster', 'value')
    _write_dict_rows(
        output,
        headers,
        [
            {
                'report_standard': CSV_STANDARD,
                'cluster': 'K8s Staging',
                'value': '=danger',
            }
        ],
    )

    raw = output.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf')
    assert b'\r\n' not in raw

    with output.open(encoding=CSV_ENCODING, newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == headers
    assert rows[0]['value'] == "'=danger"


def test_inventory_csv_schema_reuses_inventory_profiles() -> None:
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        keys = tuple(column.key for column in profile.columns)
        assert keys
        assert len(keys) == len(set(keys)), report_type
