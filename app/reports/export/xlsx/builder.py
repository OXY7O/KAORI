from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from app.reports.export.inventory_common import InventoryExportContext, get_inventory_rows
from app.reports.export.xlsx.standard import (
    INVENTORY_DATA_SHEET,
    INVENTORY_DICTIONARY_SHEET,
    INVENTORY_METADATA_SHEET,
    INVENTORY_WORKBOOK_FAMILY,
    INVENTORY_WORKBOOK_STANDARD,
    InventoryColumn,
    InventoryWorkbookProfile,
    get_inventory_workbook_profile,
)

KAORI_PRIMARY = '7C3AED'
KAORI_PRIMARY_DARK = '5B21B6'
KAORI_PRIMARY_SOFT = 'EDE9FE'
KAORI_INK = '0F172A'
KAORI_MUTED = '64748B'
KAORI_LINE = 'CBD5E1'
KAORI_LINE_LIGHT = 'E2E8F0'
KAORI_PANEL = 'F8FAFC'
KAORI_GREEN_FILL = 'DCFCE7'
KAORI_GREEN_TEXT = '166534'
KAORI_AMBER_FILL = 'FEF3C7'
KAORI_AMBER_TEXT = '92400E'
KAORI_RED_FILL = 'FEE2E2'
KAORI_RED_TEXT = '991B1B'
KAORI_BLUE_FILL = 'DBEAFE'
KAORI_BLUE_TEXT = '1E40AF'
KAORI_SLATE_FILL = 'F1F5F9'
KAORI_SLATE_TEXT = '475569'

_THIN_LINE = Side(style='thin', color=KAORI_LINE_LIGHT)
_HEADER_BORDER = Border(
    left=Side(style='thin', color=KAORI_PRIMARY_DARK),
    right=Side(style='thin', color=KAORI_PRIMARY_DARK),
    top=Side(style='thin', color=KAORI_PRIMARY_DARK),
    bottom=Side(style='thin', color=KAORI_PRIMARY_DARK),
)
_BODY_BORDER = Border(bottom=_THIN_LINE)


def build_inventory_workbook(
    *,
    report_type: str,
    payload: Mapping[str, Any],
    context: InventoryExportContext,
    output_path: Path,
) -> None:
    profile = get_inventory_workbook_profile(report_type)
    rows = get_inventory_rows(payload, profile)

    workbook = Workbook()
    inventory_sheet = workbook.active
    inventory_sheet.title = INVENTORY_DATA_SHEET
    metadata_sheet = workbook.create_sheet(INVENTORY_METADATA_SHEET)
    dictionary_sheet = workbook.create_sheet(INVENTORY_DICTIONARY_SHEET)

    _build_inventory_sheet(inventory_sheet, profile, rows)
    _build_metadata_sheet(metadata_sheet, profile, payload, context, len(rows))
    _build_dictionary_sheet(dictionary_sheet, profile)

    workbook.properties.title = f'KAORI - {profile.title}'
    workbook.properties.subject = profile.description
    workbook.properties.creator = context.generated_by or 'KAORI'
    workbook.properties.keywords = f'KAORI,{INVENTORY_WORKBOOK_FAMILY},{report_type},xlsx'
    workbook.properties.created = _naive_datetime(context.generated_at)
    workbook.properties.modified = _naive_datetime(context.generated_at)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)



def _build_inventory_sheet(
    sheet: Worksheet,
    profile: InventoryWorkbookProfile,
    rows: list[dict[str, Any]],
) -> None:
    max_column = len(profile.columns)
    last_column = get_column_letter(max_column)

    sheet.merge_cells(f'A1:{last_column}1')
    title = sheet['A1']
    title.value = f'KAORI — {profile.title}'
    title.font = Font(name='Aptos Display', size=16, bold=True, color='FFFFFF')
    title.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_DARK)
    title.alignment = Alignment(horizontal='left', vertical='center')
    sheet.row_dimensions[1].height = 30

    sheet.merge_cells(f'A2:{last_column}2')
    subtitle = sheet['A2']
    subtitle.value = profile.description
    subtitle.font = Font(name='Aptos', size=10, color=KAORI_INK)
    subtitle.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_SOFT)
    subtitle.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    sheet.row_dimensions[2].height = 28
    sheet.row_dimensions[3].height = 8

    for index, column_spec in enumerate(profile.columns, start=1):
        cell = sheet.cell(row=4, column=index, value=column_spec.label)
        cell.font = Font(name='Aptos', size=10, bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor=KAORI_PRIMARY)
        cell.border = _HEADER_BORDER
        cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = column_spec.width
    sheet.row_dimensions[4].height = 34

    start_row = 5
    for row_index, row in enumerate(rows, start=start_row):
        for column_index, column_spec in enumerate(profile.columns, start=1):
            cell = sheet.cell(
                row=row_index,
                column=column_index,
                value=_cell_value(row.get(column_spec.key), column_spec),
            )
            cell.font = Font(name='Aptos', size=9, color=KAORI_INK)
            cell.border = _BODY_BORDER
            cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            if column_spec.number_format:
                cell.number_format = column_spec.number_format
            if row_index % 2 == 0:
                cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)
        sheet.row_dimensions[row_index].height = 30

    if not rows:
        for column_index, column_spec in enumerate(profile.columns, start=1):
            value = (
                'No committed inventory rows were found for the selected reporting boundary.'
                if column_index == 1
                else None
            )
            cell = sheet.cell(row=5, column=column_index, value=value)
            cell.font = Font(
                name='Aptos',
                size=9,
                italic=column_index == 1,
                color=KAORI_MUTED,
            )
            cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)
            cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            cell.border = _BODY_BORDER
            if column_spec.number_format:
                cell.number_format = column_spec.number_format
        sheet.row_dimensions[5].height = 28

    final_row = max(start_row, start_row + len(rows) - 1)
    table = Table(
        displayName=f'{_safe_table_name(profile.report_type)}InventoryTable',
        ref=f'A4:{last_column}{final_row}',
    )
    table.tableStyleInfo = TableStyleInfo(
        name='TableStyleMedium4',
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=False,
        showColumnStripes=False,
    )
    sheet.add_table(table)
    sheet.auto_filter.ref = f'A4:{last_column}{final_row}'
    sheet.freeze_panes = profile.freeze_panes
    sheet.sheet_view.showGridLines = False
    sheet.auto_filter.ref = f'A4:{last_column}{final_row}'

    _apply_status_conditional_formatting(sheet, profile, start_row, max(start_row, final_row))


def _build_metadata_sheet(
    sheet: Worksheet,
    profile: InventoryWorkbookProfile,
    payload: Mapping[str, Any],
    context: InventoryExportContext,
    row_count: int,
) -> None:
    sheet.merge_cells('A1:D1')
    title = sheet['A1']
    title.value = 'KAORI Inventory Workbook Metadata'
    title.font = Font(name='Aptos Display', size=16, bold=True, color='FFFFFF')
    title.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_DARK)
    title.alignment = Alignment(horizontal='left', vertical='center')
    sheet.row_dimensions[1].height = 30

    headers = ('Field', 'Value', 'Applies To', 'Notes')
    for index, label in enumerate(headers, start=1):
        cell = sheet.cell(row=3, column=index, value=label)
        _style_header_cell(cell)
    sheet.row_dimensions[3].height = 28

    metadata = [
        ('Workbook Standard', INVENTORY_WORKBOOK_STANDARD, 'All sheets', 'Canonical reusable KAORI Inventory Excel contract.'),
        ('Report Reference', str(context.report_id), 'Workbook', 'Stable KAORI document reference; the internal database key is not exposed.'),
        ('Report Name', context.report_name, 'Workbook', 'User-visible report request name.'),
        ('Report Type', context.report_type, 'Workbook', profile.title),
        ('Report Family', INVENTORY_WORKBOOK_FAMILY, 'Workbook', 'Inventory is table-first and excludes analytical recommendations.'),
        ('Primary Format', 'XLSX', 'Workbook', 'Native Excel workbook with tables, filters, freeze panes, and field dictionary.'),
        ('Generated At', context.generated_at, 'Workbook', 'Artifact generation timestamp.'),
        ('Generated By', context.generated_by or 'Not Available', 'Workbook', 'Persisted report owner snapshot.'),
        ('Classification', context.classification, 'Workbook', 'Report classification.'),
        ('Cluster Scope', context.cluster_scope, 'Inventory', 'Selected cluster boundary.'),
        ('Namespace Scope', context.namespace_scope, 'Inventory', 'Selected namespace boundary.'),
        ('Reporting Period', context.period_label, 'Inventory', 'Inventory workbooks use the committed snapshot period.'),
        ('Data Cut-off', context.data_cutoff or payload.get('data_cutoff') or payload.get('collected_at'), 'Inventory', 'Committed evidence cut-off.'),
        ('Source', context.source_label, 'Inventory', 'No live Kubernetes API call is performed during workbook generation.'),
        ('Total Rows', row_count, 'Inventory', 'Number of committed rows exported.'),
        ('Missing Text Rule', 'Not Available', 'Inventory', 'Missing text evidence remains explicit.'),
        ('Missing Numeric Rule', 'Blank', 'Inventory', 'Numeric columns remain numeric and sortable.'),
        ('Horizontal Alignment', 'Left', 'Inventory', 'Canonical KAORI table alignment.'),
        ('Vertical Alignment', 'Middle', 'Inventory', 'Text is vertically centered in every table row.'),
        ('Private Key Export', 'Excluded', 'TLS Inventory', 'tls.key, Secret values, and recoverable key material are never exported.'),
    ]

    for row_index, metadata_row in enumerate(metadata, start=4):
        for column_index, value in enumerate(metadata_row, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=_metadata_value(value))
            _style_body_cell(cell, alternate=row_index % 2 == 0)
            if isinstance(value, datetime):
                cell.number_format = 'yyyy-mm-dd hh:mm'
        sheet.row_dimensions[row_index].height = 26

    end_row = 3 + len(metadata)
    table = Table(displayName='InventoryWorkbookMetadataTable', ref=f'A3:D{end_row}')
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium4', showRowStripes=False)
    sheet.add_table(table)
    sheet.freeze_panes = 'A4'
    sheet.sheet_view.showGridLines = False
    for column, width in {'A': 25, 'B': 40, 'C': 22, 'D': 58}.items():
        sheet.column_dimensions[column].width = width


def _build_dictionary_sheet(
    sheet: Worksheet,
    profile: InventoryWorkbookProfile,
) -> None:
    sheet.merge_cells('A1:F1')
    title = sheet['A1']
    title.value = 'KAORI Inventory Field Dictionary'
    title.font = Font(name='Aptos Display', size=16, bold=True, color='FFFFFF')
    title.fill = PatternFill('solid', fgColor=KAORI_PRIMARY_DARK)
    title.alignment = Alignment(horizontal='left', vertical='center')
    sheet.row_dimensions[1].height = 30

    headers = ('Report Type', 'Column', 'Definition', 'Data Type', 'Source / Rule', 'Missing Value Rule')
    for index, label in enumerate(headers, start=1):
        cell = sheet.cell(row=3, column=index, value=label)
        _style_header_cell(cell)
    sheet.row_dimensions[3].height = 28

    for row_index, column_spec in enumerate(profile.columns, start=4):
        values = (
            profile.report_type,
            column_spec.label,
            column_spec.definition,
            column_spec.data_type,
            column_spec.source,
            column_spec.missing_value_rule,
        )
        for column_index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=value)
            _style_body_cell(cell, alternate=row_index % 2 == 0)
        sheet.row_dimensions[row_index].height = 30

    end_row = 3 + len(profile.columns)
    table = Table(displayName=f'{_safe_table_name(profile.report_type)}FieldDictionaryTable', ref=f'A3:F{end_row}')
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium4', showRowStripes=False)
    sheet.add_table(table)
    sheet.freeze_panes = 'A4'
    sheet.sheet_view.showGridLines = False
    for column, width in {'A': 24, 'B': 28, 'C': 58, 'D': 16, 'E': 36, 'F': 22}.items():
        sheet.column_dimensions[column].width = width


def _style_header_cell(cell: Any) -> None:
    cell.font = Font(name='Aptos', size=10, bold=True, color='FFFFFF')
    cell.fill = PatternFill('solid', fgColor=KAORI_PRIMARY)
    cell.border = _HEADER_BORDER
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)


def _style_body_cell(cell: Any, *, alternate: bool) -> None:
    cell.font = Font(name='Aptos', size=9, color=KAORI_INK)
    cell.border = _BODY_BORDER
    cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    if alternate:
        cell.fill = PatternFill('solid', fgColor=KAORI_PANEL)


def _cell_value(value: Any, column_spec: InventoryColumn) -> Any:
    if value is None or value == '':
        if column_spec.data_type in {'integer', 'number', 'decimal'}:
            return None
        return 'Not Available'

    if column_spec.data_type == 'boolean':
        if isinstance(value, bool):
            return 'Yes' if value else 'No'
        return value

    if column_spec.data_type in {'integer', 'number', 'decimal'}:
        return _numeric_value(value)

    if column_spec.data_type in {'datetime', 'date'}:
        if isinstance(value, datetime):
            return _naive_datetime(value)
        if isinstance(value, date):
            return value
        return value

    if isinstance(value, (list, tuple, set)):
        rendered = ', '.join(str(item) for item in value if item not in {None, ''})
        return rendered or 'Not Available'
    if isinstance(value, Mapping):
        rendered = ', '.join(f'{key}={item}' for key, item in sorted(value.items()))
        return rendered or 'Not Available'
    return value


def _numeric_value(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    rendered = str(value).strip()
    if not rendered or rendered.lower() in {'not available', 'unknown', '-'}:
        return None
    try:
        number = float(rendered)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _metadata_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _naive_datetime(value)
    if value is None or value == '':
        return 'Not Available'
    return value


def _naive_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _safe_table_name(report_type: str) -> str:
    return ''.join(part.title() for part in report_type.replace('-', '_').split('_'))


def _apply_status_conditional_formatting(
    sheet: Worksheet,
    profile: InventoryWorkbookProfile,
    start_row: int,
    end_row: int,
) -> None:
    label_to_index = {column.key: index for index, column in enumerate(profile.columns, start=1)}
    for key in profile.status_columns:
        column_index = label_to_index.get(key)
        if column_index is None:
            continue
        letter = get_column_letter(column_index)
        range_ref = f'{letter}{start_row}:{letter}{max(start_row, end_row)}'
        first_cell = f'{letter}{start_row}'
        for values, fill, font in (
            (
                ('Ready', 'Yes', 'Current', 'Valid', 'In Use', 'Fully Covered', 'Passed', 'Schedulable', 'Discovered'),
                KAORI_GREEN_FILL,
                KAORI_GREEN_TEXT,
            ),
            (
                ('Review', 'Warning', 'Renewal Window', 'Expiring Soon', 'Unknown Usage', 'Partial Coverage', 'Stale'),
                KAORI_AMBER_FILL,
                KAORI_AMBER_TEXT,
            ),
            (
                ('Critical', 'Critical Expiry', 'Expired', 'Invalid', 'Failed', 'Unavailable', 'Not Ready', 'No'),
                KAORI_RED_FILL,
                KAORI_RED_TEXT,
            ),
            (
                ('Unused', 'Information', 'Query Ready'),
                KAORI_BLUE_FILL,
                KAORI_BLUE_TEXT,
            ),
            (
                ('Unknown', 'Not Available', 'Not Collected', 'Not Reported', 'TLS Disabled'),
                KAORI_SLATE_FILL,
                KAORI_SLATE_TEXT,
            ),
        ):
            expression = ','.join(f'"{value}"' for value in values)
            formula = f'ISNUMBER(MATCH({first_cell},{{{expression}}},0))'
            sheet.conditional_formatting.add(
                range_ref,
                FormulaRule(
                    formula=[formula],
                    fill=PatternFill('solid', fgColor=fill),
                    font=Font(color=font, bold=True),
                ),
            )

    days_index = label_to_index.get('days_remaining')
    if days_index:
        letter = get_column_letter(days_index)
        range_ref = f'{letter}{start_row}:{letter}{max(start_row, end_row)}'
        sheet.conditional_formatting.add(
            range_ref,
            CellIsRule(operator='lessThan', formula=['0'], fill=PatternFill('solid', fgColor=KAORI_RED_FILL), font=Font(color=KAORI_RED_TEXT, bold=True)),
        )
        sheet.conditional_formatting.add(
            range_ref,
            CellIsRule(operator='between', formula=['0', '7'], fill=PatternFill('solid', fgColor=KAORI_RED_FILL), font=Font(color=KAORI_RED_TEXT, bold=True)),
        )
        sheet.conditional_formatting.add(
            range_ref,
            CellIsRule(operator='between', formula=['8', '30'], fill=PatternFill('solid', fgColor=KAORI_AMBER_FILL), font=Font(color=KAORI_AMBER_TEXT, bold=True)),
        )
