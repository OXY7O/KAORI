from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.reports.export.inventory_common import InventoryExportContext
from app.reports.export.tabular import TABULAR_EXPORT_STANDARD, TABULAR_SCHEMA_VERSION
from app.reports.export.xlsx.builder import (
    DATA_START_ROW,
    HEADER_ROW,
    _inventory_print_width,
    build_inventory_workbook,
    validate_inventory_xlsx_artifact,
)
from app.reports.export.xlsx.standard import (
    INVENTORY_DATA_SHEET,
    INVENTORY_DICTIONARY_SHEET,
    INVENTORY_METADATA_SHEET,
    INVENTORY_OVERVIEW_SHEET,
    INVENTORY_WORKBOOK_PROFILES,
    INVENTORY_WORKBOOK_STANDARD,
    XLSX_REPORTING_STANDARD,
)

EXPECTED_REPORT_TYPES = {
    'inventory_overview',
    'node_inventory',
    'namespace_inventory',
    'workload_inventory',
    'pod_inventory',
    'service_inventory',
    'ingress_inventory',
    'configuration_inventory',
    'storage_inventory',
    'object_storage_inventory',
    'tls_inventory',
}


def _sample_value(data_type: str, key: str) -> object:
    if data_type == 'datetime':
        return datetime(2026, 8, 3, 7, 47, tzinfo=UTC)
    if data_type == 'date':
        return datetime(2026, 8, 3, tzinfo=UTC).date()
    if data_type in {'integer', 'number', 'decimal'}:
        return 1
    if data_type == 'boolean':
        return True
    if key in {'status', 'inventory_status'}:
        return 'Current'
    if key == 'ready':
        return 'Ready'
    if key == 'status_label':
        return 'Valid'
    if key == 'usage_label':
        return 'In Use'
    if key == 'coverage_label':
        return 'Fully Covered'
    if key == 'parse_state':
        return 'Passed'
    return f'Sample {key.replace("_", " ")}'


def _payload(report_type: str) -> dict[str, object]:
    profile = INVENTORY_WORKBOOK_PROFILES[report_type]
    row: dict[str, object] = {}
    for column in profile.columns:
        source_key = column.source_key or column.key
        if column.scale_divisor:
            row[source_key] = column.scale_divisor * 2.5
        else:
            row[source_key] = _sample_value(column.data_type, source_key)
    return {
        profile.row_source: [row],
        'data_cutoff': datetime(2026, 8, 3, 7, 57, tzinfo=UTC),
        'collected_at': datetime(2026, 8, 3, 7, 47, tzinfo=UTC),
    }


def _context(report_type: str) -> InventoryExportContext:
    return InventoryExportContext(
        report_id='KAORI-INV-NOD-20260803-ABCDEF12',
        report_name=f'{report_type} validation',
        report_type=report_type,
        generated_at=datetime(2026, 8, 3, 8, 0, tzinfo=UTC),
        generated_by='Platform Operations',
        cluster_scope='K8s PGN Staging',
        namespace_scope='All Namespaces',
        period_label='Current Inventory Snapshot',
        data_cutoff=datetime(2026, 8, 3, 7, 57, tzinfo=UTC),
    )


def test_inventory_workbook_profiles_cover_every_supported_inventory_report() -> None:
    assert set(INVENTORY_WORKBOOK_PROFILES) == EXPECTED_REPORT_TYPES


def test_every_inventory_profile_declares_a_global_overview_chart() -> None:
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        assert profile.overview_chart is not None, report_type

        column_keys = {column.key for column in profile.columns}
        chart = profile.overview_chart
        assert chart.category_key in column_keys, report_type
        if chart.aggregation == 'value':
            assert chart.value_key in column_keys, report_type
        else:
            assert chart.aggregation == 'count', report_type
            assert chart.value_key is None, report_type


def test_identity_columns_are_leading_and_reusable_across_csv_xlsx() -> None:
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        keys = tuple(column.key for column in profile.columns)
        assert keys[: len(profile.identity_columns)] == profile.identity_columns, report_type


def test_status_semantics_are_owned_by_columns() -> None:
    node_profile = INVENTORY_WORKBOOK_PROFILES['node_inventory']
    semantics = {column.key: column.semantic_type for column in node_profile.columns}
    assert semantics['ready'] == 'readiness'
    assert semantics['inventory_status'] == 'inventory_state'
    assert semantics['scheduling_state'] == 'scheduling'
    assert semantics['memory_pressure'] == 'negative_condition'
    assert semantics['disk_pressure'] == 'negative_condition'


def test_all_inventory_workbooks_follow_the_reusable_four_sheet_contract(tmp_path: Path) -> None:
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        output_path = tmp_path / f'{report_type}.xlsx'
        build_inventory_workbook(
            report_type=report_type,
            payload=_payload(report_type),
            context=_context(report_type),
            output_path=output_path,
        )

        workbook = load_workbook(output_path)
        assert workbook.sheetnames == [
            INVENTORY_OVERVIEW_SHEET,
            INVENTORY_DATA_SHEET,
            INVENTORY_METADATA_SHEET,
            INVENTORY_DICTIONARY_SHEET,
        ]

        summary = workbook[INVENTORY_OVERVIEW_SHEET]
        assert summary['A1'].value == f'KAORI — {profile.title} Overview'
        assert summary['A4'].value == 'Key Metrics'
        assert summary['A5'].value == 'Records'
        assert summary['A6'].value == 1
        assert summary['A8'].value == 'General Information'
        assert summary['F8'].value == 'Workbook Navigation'
        assert summary['F9'].value == 'Inventory'
        assert summary['F9'].hyperlink.target == "#'Inventory'!A1"
        assert summary['F10'].value == 'Metadata'
        assert summary['F10'].hyperlink.target == "#'Metadata'!A1"
        assert summary['F11'].value == 'Field Dictionary'
        assert summary['F11'].hyperlink.target == "#'Field Dictionary'!A1"
        assert summary['A18'].value == 'Visual Summary'
        assert len(summary._charts) == 1

        inventory = workbook[INVENTORY_DATA_SHEET]
        expected_freeze_column = get_column_letter(max(1, len(profile.identity_columns) + 1))
        assert inventory.freeze_panes == f'{expected_freeze_column}{DATA_START_ROW}'
        assert inventory.auto_filter.ref is not None
        assert len(inventory.tables) == 1
        assert inventory['A1'].value == f'KAORI — {profile.title}'
        assert inventory['A3'].value.startswith('Reference: KAORI-INV-')
        assert inventory.cell(row=HEADER_ROW, column=1).value == profile.columns[0].label
        assert inventory.print_title_rows == f'$1:${HEADER_ROW}'
        assert inventory.page_setup.fitToWidth == _inventory_print_width(len(profile.columns))

        for row in inventory.iter_rows(
            min_row=HEADER_ROW,
            max_row=DATA_START_ROW,
            max_col=len(profile.columns),
        ):
            for cell in row:
                assert cell.alignment.horizontal == 'left'
                assert cell.alignment.vertical == 'center'
                assert cell.alignment.wrap_text is True

        metadata = workbook[INVENTORY_METADATA_SHEET]
        metadata_values = {
            metadata.cell(row=row, column=1).value: metadata.cell(row=row, column=2).value
            for row in range(5, metadata.max_row + 1)
        }
        assert metadata_values['Workbook Standard'] == INVENTORY_WORKBOOK_STANDARD
        assert metadata_values['XLSX Standard'] == XLSX_REPORTING_STANDARD
        assert metadata_values['Tabular Standard'] == TABULAR_EXPORT_STANDARD
        assert metadata_values['Schema Version'] == TABULAR_SCHEMA_VERSION
        assert metadata_values['Primary Format'] == 'XLSX'
        assert metadata_values['CSV Parity'] == 'Enabled'

        dictionary = workbook[INVENTORY_DICTIONARY_SHEET]
        assert dictionary.max_row == len(profile.columns) + 4
        assert dictionary.max_column == 9
        assert len(dictionary.tables) == 1


def test_distribution_overview_chart_aggregates_records_by_category(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    profile = INVENTORY_WORKBOOK_PROFILES[report_type]
    output_path = tmp_path / 'nodes-overview-distribution.xlsx'
    payload = _payload(report_type)
    source_rows = payload[profile.row_source]
    assert isinstance(source_rows, list)
    base_row = dict(source_rows[0])
    rows = []
    for index, readiness in enumerate(('Ready', 'Not Ready', 'Ready'), start=1):
        row = dict(base_row)
        row['node'] = f'node-{index}'
        row['ready'] = readiness
        rows.append(row)
    payload[profile.row_source] = rows

    build_inventory_workbook(
        report_type=report_type,
        payload=payload,
        context=_context(report_type),
        output_path=output_path,
    )

    workbook = load_workbook(output_path)
    summary = workbook[INVENTORY_OVERVIEW_SHEET]
    assert summary['A19'].value == 'Ready'
    assert summary['B19'].value == 'Records'
    assert summary['A20'].value == 'Ready'
    assert summary['B20'].value == 2
    assert summary['A21'].value == 'Not Ready'
    assert summary['B21'].value == 1
    assert summary['B20'].number_format == '#,##0'
    assert len(summary._charts) == 1



def test_runtime_xlsx_artifact_validator_accepts_the_global_contract(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    output_path = tmp_path / 'nodes-runtime-contract.xlsx'
    build_inventory_workbook(
        report_type=report_type,
        payload=_payload(report_type),
        context=_context(report_type),
        output_path=output_path,
    )

    validate_inventory_xlsx_artifact(output_path)


def test_runtime_xlsx_artifact_validator_rejects_missing_overview(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    output_path = tmp_path / 'nodes-missing-overview.xlsx'
    build_inventory_workbook(
        report_type=report_type,
        payload=_payload(report_type),
        context=_context(report_type),
        output_path=output_path,
    )
    workbook = load_workbook(output_path)
    workbook.remove(workbook[INVENTORY_OVERVIEW_SHEET])
    workbook.save(output_path)

    with pytest.raises(ValueError, match='Overview'):
        validate_inventory_xlsx_artifact(output_path)


def test_runtime_xlsx_artifact_validator_rejects_missing_visual_summary(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    output_path = tmp_path / 'nodes-missing-chart.xlsx'
    build_inventory_workbook(
        report_type=report_type,
        payload=_payload(report_type),
        context=_context(report_type),
        output_path=output_path,
    )
    workbook = load_workbook(output_path)
    workbook[INVENTORY_OVERVIEW_SHEET]._charts.clear()
    workbook.save(output_path)

    with pytest.raises(ValueError, match='chart'):
        validate_inventory_xlsx_artifact(output_path)


def test_runtime_xlsx_artifact_validator_rejects_stale_workbook_standard(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    output_path = tmp_path / 'nodes-stale-standard.xlsx'
    build_inventory_workbook(
        report_type=report_type,
        payload=_payload(report_type),
        context=_context(report_type),
        output_path=output_path,
    )
    workbook = load_workbook(output_path)
    metadata = workbook[INVENTORY_METADATA_SHEET]
    for row in range(5, metadata.max_row + 1):
        if metadata.cell(row=row, column=1).value == 'Workbook Standard':
            metadata.cell(row=row, column=2).value = 'kaori-inventory-xlsx-v2.0'
            break
    workbook.save(output_path)

    with pytest.raises(ValueError, match='Workbook Standard'):
        validate_inventory_xlsx_artifact(output_path)


def test_object_storage_workbook_uses_readable_gib_columns(tmp_path: Path) -> None:
    report_type = 'object_storage_inventory'
    profile = INVENTORY_WORKBOOK_PROFILES[report_type]
    output_path = tmp_path / 'object-storage.xlsx'
    payload = _payload(report_type)

    build_inventory_workbook(
        report_type=report_type,
        payload=payload,
        context=_context(report_type),
        output_path=output_path,
    )

    workbook = load_workbook(output_path)
    inventory = workbook[INVENTORY_DATA_SHEET]
    headers = [inventory.cell(row=HEADER_ROW, column=index).value for index in range(1, len(profile.columns) + 1)]
    assert 'Usage GiB' in headers
    assert 'Quota GiB' in headers
    assert 'Usage Bytes' not in headers
    assert 'Quota Bytes' not in headers
    usage_index = headers.index('Usage GiB') + 1
    quota_index = headers.index('Quota GiB') + 1
    assert inventory.cell(row=DATA_START_ROW, column=usage_index).value == 2.5
    assert inventory.cell(row=DATA_START_ROW, column=quota_index).value == 2.5
    utilization_index = headers.index('Quota Utilization %') + 1
    assert inventory.cell(row=DATA_START_ROW, column=utilization_index).value == 100.0

def test_numeric_missing_values_stay_blank_and_text_missing_values_are_explicit(tmp_path: Path) -> None:
    report_type = 'node_inventory'
    profile = INVENTORY_WORKBOOK_PROFILES[report_type]
    output_path = tmp_path / 'nodes-empty-fields.xlsx'
    row = {column.key: None for column in profile.columns}

    build_inventory_workbook(
        report_type=report_type,
        payload={profile.row_source: [row]},
        context=_context(report_type),
        output_path=output_path,
    )

    workbook = load_workbook(output_path)
    inventory = workbook[INVENTORY_DATA_SHEET]
    for index, column in enumerate(profile.columns, start=1):
        value = inventory.cell(row=DATA_START_ROW, column=index).value
        if column.data_type in {'integer', 'number', 'decimal'}:
            assert value is None
        else:
            assert value == 'Not Available'


def test_tls_inventory_never_exports_private_key_or_secret_values(tmp_path: Path) -> None:
    profile = INVENTORY_WORKBOOK_PROFILES['tls_inventory']
    labels = {column.label.lower() for column in profile.columns}
    keys = {column.key.lower() for column in profile.columns}
    forbidden = {'private key', 'tls.key', 'secret value', 'secret data', 'raw secret'}

    assert not labels.intersection(forbidden)
    assert not keys.intersection({'private_key', 'tls_key', 'secret_value', 'secret_data'})

    output_path = tmp_path / 'tls-inventory.xlsx'
    build_inventory_workbook(
        report_type='tls_inventory',
        payload=_payload('tls_inventory'),
        context=_context('tls_inventory'),
        output_path=output_path,
    )
    workbook = load_workbook(output_path)
    metadata = workbook[INVENTORY_METADATA_SHEET]
    metadata_values = {
        metadata.cell(row=row, column=1).value: metadata.cell(row=row, column=2).value
        for row in range(5, metadata.max_row + 1)
    }
    assert metadata_values['Private Key Export'] == 'Excluded'


def test_empty_inventory_workbook_keeps_a_valid_unmerged_excel_table(tmp_path: Path) -> None:
    output_path = tmp_path / 'empty-services.xlsx'
    build_inventory_workbook(
        report_type='service_inventory',
        payload={'inventory_assets': []},
        context=_context('service_inventory'),
        output_path=output_path,
    )

    workbook = load_workbook(output_path)
    inventory = workbook[INVENTORY_DATA_SHEET]
    assert inventory.cell(row=DATA_START_ROW, column=1).value == (
        'No committed inventory rows were found for the selected reporting boundary.'
    )
    assert not any(str(DATA_START_ROW) in str(cell_range) for cell_range in inventory.merged_cells.ranges)
    assert len(inventory.tables) == 1
