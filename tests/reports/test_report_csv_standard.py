from __future__ import annotations

import csv
from pathlib import Path

from app.reports.export.csv.renderer import (
    _write_dict_rows,
    build_analytics_csv_records,
    normalize_analytics_scalar,
)
from app.reports.export.csv.standard import (
    ANALYTICS_HEADERS,
    COMMON_METADATA_HEADERS,
    CSV_CONTENT_TYPE,
    CSV_ENCODING,
    CSV_INTERCHANGE_PROFILE,
    CSV_STANDARD,
    INVENTORY_CONTROL_HEADERS,
    protect_spreadsheet_formula,
)
from app.reports.export.html_pdf.document import (
    ReportDocument,
    ReportFinding,
    ReportMetric,
    ReportSection,
    ReportTable,
)
from app.reports.export.tabular import TABULAR_EXPORT_STANDARD, serialize_tabular_value
from app.reports.export.xlsx.standard import INVENTORY_WORKBOOK_PROFILES


def test_csv_standard_has_stable_v3_metadata_and_record_contract() -> None:
    assert CSV_STANDARD == 'kaori-reporting-csv-v3.0'
    assert CSV_INTERCHANGE_PROFILE == 'portable-tabular-v1'
    assert CSV_CONTENT_TYPE == 'text/csv; charset=utf-8'
    assert COMMON_METADATA_HEADERS[0:5] == (
        'format_standard',
        'tabular_standard',
        'schema_version',
        'interchange_profile',
        'document_reference',
    )
    assert ANALYTICS_HEADERS[: len(COMMON_METADATA_HEADERS)] == COMMON_METADATA_HEADERS
    assert ANALYTICS_HEADERS[len(COMMON_METADATA_HEADERS) :] == (
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
        'unit',
        'value_type',
        'status',
        'tone',
        'note',
    )
    assert INVENTORY_CONTROL_HEADERS == ('record_type', 'record_reference', 'row_number')
    assert TABULAR_EXPORT_STANDARD == 'kaori-tabular-export-v3.0'


def test_analytics_csv_separates_simple_numeric_units() -> None:
    assert normalize_analytics_scalar('17.48 GiB') == (17.48, 'GiB')
    assert normalize_analytics_scalar('56.2%') == (56.2, '%')
    assert normalize_analytics_scalar('0.14 cores') == (0.14, 'cores')
    assert normalize_analytics_scalar('Not Available') == ('Not Available', '')


def test_csv_formula_controls_are_escaped() -> None:
    for value in ('=1+1', '+cmd', '-cmd', '@SUM(A1:A2)', '  =1+1'):
        assert protect_spreadsheet_formula(value).startswith("'")
    assert protect_spreadsheet_formula('normal') == 'normal'
    assert protect_spreadsheet_formula('42') == '42'
    assert protect_spreadsheet_formula('-42.5') == '-42.5'
    assert protect_spreadsheet_formula('+3.2e4') == '+3.2e4'


def test_csv_writer_uses_utf8_bom_lf_and_stable_header_order(tmp_path: Path) -> None:
    output = tmp_path / 'report.csv'
    headers = ('format_standard', 'cluster', 'value')
    _write_dict_rows(
        output,
        headers,
        [
            {
                'format_standard': CSV_STANDARD,
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


def test_csv_writer_preserves_negative_numeric_values(tmp_path: Path) -> None:
    output = tmp_path / 'negative-number.csv'
    _write_dict_rows(output, ('value',), [{'value': -42.5}, {'value': '-17.25'}])

    with output.open(encoding=CSV_ENCODING, newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]['value'] == '-42.5'
    assert rows[1]['value'] == '-17.25'


def test_nested_csv_values_use_deterministic_json() -> None:
    assert serialize_tabular_value({'b': 2, 'a': 1}) == '{"a":1,"b":2}'
    assert serialize_tabular_value(['a', 'b']) == '["a","b"]'


def test_analytics_csv_records_keep_stable_references_and_field_order() -> None:
    document = ReportDocument(
        report_id='KAORI-ANL-AOV-20260805-ABCDEF12',
        report_name='Analytics Overview',
        report_type_label='Analytics Overview',
        report_description='Description',
        report_domain_label='Kubernetes',
        source_kind_label='Analytics Materialized Snapshot',
        cluster_scope='K8s PGN Staging',
        namespace_scope='All Namespaces',
        period_label='Last 30 Days',
        generated_at='05 Aug 2026 02:30 UTC',
        data_cutoff='05 Aug 2026 02:15 UTC',
        generated_by='Platform Operations',
        classification='Internal',
        retention_label='90 Days',
        overall_posture='Review',
        overall_tone='warning',
        source_metrics=(ReportMetric('Coverage', '100%', 'Committed', 'success'),),
        sections=(
            ReportSection(
                key='executive_summary',
                number=1,
                title='Executive Summary',
                description='Summary',
                status_label='Review',
                status_tone='warning',
                metrics=(ReportMetric('Findings', '2'),),
                findings=(ReportFinding('Review capacity', 'Validate headroom.'),),
                tables=(
                    ReportTable(
                        title='Decision Register',
                        columns=('Ref.', 'Decision', 'Status'),
                        rows=(('R1', 'Review capacity', 'Open'),),
                    ),
                ),
            ),
        ),
        methodology_notes=('Use committed evidence.',),
        template_label='Analytics Overview',
    )

    records = build_analytics_csv_records(document)
    table_records = [record for record in records if record.dataset == 'decision_register']
    assert {record.record_reference for record in table_records} == {'R1'}
    assert [record.field_order for record in table_records] == [1, 2, 3]
    assert records[0].record_reference == 'SRC-M01'
    assert records[-1].record_reference == 'MET-N01'


def test_inventory_csv_schema_reuses_inventory_profiles() -> None:
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        keys = tuple(column.key for column in profile.columns)
        assert keys
        assert len(keys) == len(set(keys)), report_type
        assert keys[: len(profile.identity_columns)] == profile.identity_columns


def test_csv_output_is_detectable_and_round_trips_with_standard_library(tmp_path: Path) -> None:
    output = tmp_path / 'portable.csv'
    headers = ('record_reference', 'name', 'value', 'unit', 'observed_at')
    rows = [
        {
            'record_reference': 'R1',
            'name': 'bucket, primary',
            'value': 17.48,
            'unit': 'GiB',
            'observed_at': '2026-08-26T05:00:00+00:00',
        },
        {
            'record_reference': 'R2',
            'name': 'line\nbreak',
            'value': '',
            'unit': 'GiB',
            'observed_at': '',
        },
    ]
    _write_dict_rows(output, headers, rows)

    raw = output.read_text(encoding=CSV_ENCODING)
    dialect = csv.Sniffer().sniff(raw[:4096], delimiters=',')
    assert dialect.delimiter == ','
    with output.open(encoding=CSV_ENCODING, newline='') as handle:
        parsed = list(csv.DictReader(handle, dialect=dialect))
    assert tuple(parsed[0]) == headers
    assert parsed[0]['name'] == 'bucket, primary'
    assert parsed[0]['value'] == '17.48'
    assert parsed[0]['unit'] == 'GiB'
    assert parsed[1]['name'] == 'line\nbreak'
    assert parsed[1]['value'] == ''
