from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openpyxl import load_workbook

from app.reports.export.inventory_common import InventoryExportContext
from app.reports.export.xlsx.builder import build_inventory_workbook
from app.reports.export.xlsx.standard import (
    INVENTORY_DATA_SHEET,
    INVENTORY_DICTIONARY_SHEET,
    INVENTORY_METADATA_SHEET,
    INVENTORY_WORKBOOK_PROFILES,
    INVENTORY_WORKBOOK_STANDARD,
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
    row = {column.key: _sample_value(column.data_type, column.key) for column in profile.columns}
    return {
        profile.row_source: [row],
        'data_cutoff': datetime(2026, 8, 3, 7, 57, tzinfo=UTC),
        'collected_at': datetime(2026, 8, 3, 7, 47, tzinfo=UTC),
    }


def _context(report_type: str) -> InventoryExportContext:
    return InventoryExportContext(
        report_id=701,
        report_name=f'{report_type} validation',
        report_type=report_type,
        generated_at=datetime(2026, 8, 3, 8, 0, tzinfo=UTC),
        generated_by='Platform Operations',
        cluster_scope='K8s PGN Staging',
        namespace_scope='All Namespaces',
        period_label='Current Inventory Snapshot',
        data_cutoff=datetime(2026, 8, 3, 7, 57, tzinfo=UTC),
    )


def test_inventory_workbook_profiles_are_exactly_the_ten_supported_reports() -> None:
    assert set(INVENTORY_WORKBOOK_PROFILES) == EXPECTED_REPORT_TYPES


def test_all_inventory_workbooks_follow_the_reusable_three_sheet_contract(tmp_path: Path) -> None:
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
            INVENTORY_DATA_SHEET,
            INVENTORY_METADATA_SHEET,
            INVENTORY_DICTIONARY_SHEET,
        ]

        inventory = workbook[INVENTORY_DATA_SHEET]
        assert inventory.freeze_panes == profile.freeze_panes
        assert inventory.auto_filter.ref is not None
        assert len(inventory.tables) == 1
        assert inventory['A1'].value == f'KAORI — {profile.title}'
        assert inventory['A4'].value == profile.columns[0].label

        for row in inventory.iter_rows(min_row=4, max_row=5, max_col=len(profile.columns)):
            for cell in row:
                assert cell.alignment.horizontal == 'left'
                assert cell.alignment.vertical == 'center'
                assert cell.alignment.wrap_text is True

        metadata = workbook[INVENTORY_METADATA_SHEET]
        metadata_values = {metadata.cell(row=row, column=1).value: metadata.cell(row=row, column=2).value for row in range(4, metadata.max_row + 1)}
        assert metadata_values['Workbook Standard'] == INVENTORY_WORKBOOK_STANDARD
        assert metadata_values['Primary Format'] == 'XLSX'
        assert metadata_values['Horizontal Alignment'] == 'Left'
        assert metadata_values['Vertical Alignment'] == 'Middle'

        dictionary = workbook[INVENTORY_DICTIONARY_SHEET]
        assert dictionary.max_row == len(profile.columns) + 3
        assert len(dictionary.tables) == 1


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
        value = inventory.cell(row=5, column=index).value
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
    metadata_values = {metadata.cell(row=row, column=1).value: metadata.cell(row=row, column=2).value for row in range(4, metadata.max_row + 1)}
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
    assert inventory['A5'].value == 'No committed inventory rows were found for the selected reporting boundary.'
    assert not any('5' in str(cell_range) for cell_range in inventory.merged_cells.ranges)
    assert len(inventory.tables) == 1
