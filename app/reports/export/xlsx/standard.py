from __future__ import annotations

from app.reports.export.xlsx.profiles_infrastructure import INFRASTRUCTURE_INVENTORY_WORKBOOK_PROFILES
from app.reports.export.xlsx.profiles_kubernetes import KUBERNETES_INVENTORY_WORKBOOK_PROFILES
from app.reports.export.xlsx.schema import (
    INVENTORY_DATA_SHEET,
    INVENTORY_DICTIONARY_SHEET,
    INVENTORY_METADATA_SHEET,
    INVENTORY_OVERVIEW_SHEET,
    INVENTORY_WORKBOOK_FAMILY,
    INVENTORY_WORKBOOK_STANDARD,
    XLSX_REPORTING_STANDARD,
    InventoryColumn,
    InventoryOverviewChart,
    InventoryWorkbookProfile,
    column,
)

__all__ = (
    'INVENTORY_DATA_SHEET',
    'INVENTORY_DICTIONARY_SHEET',
    'INVENTORY_METADATA_SHEET',
    'INVENTORY_OVERVIEW_SHEET',
    'INVENTORY_WORKBOOK_FAMILY',
    'INVENTORY_WORKBOOK_PROFILES',
    'INVENTORY_WORKBOOK_STANDARD',
    'INVENTORY_XLSX_REPORT_TYPES',
    'XLSX_REPORTING_STANDARD',
    'InventoryColumn',
    'InventoryOverviewChart',
    'InventoryWorkbookProfile',
    'column',
    'get_inventory_workbook_profile',
)

INVENTORY_WORKBOOK_PROFILES: dict[str, InventoryWorkbookProfile] = {
    **KUBERNETES_INVENTORY_WORKBOOK_PROFILES,
    **INFRASTRUCTURE_INVENTORY_WORKBOOK_PROFILES,
}


def _validate_inventory_workbook_profiles() -> None:
    numeric_types = {'integer', 'number', 'decimal'}
    for report_type, profile in INVENTORY_WORKBOOK_PROFILES.items():
        if profile.report_type != report_type:
            raise ValueError(
                f'Inventory XLSX profile registry key {report_type!r} does not match '
                f'profile report type {profile.report_type!r}.'
            )

        columns = {column.key: column for column in profile.columns}
        chart = profile.overview_chart
        if chart.category_key not in columns:
            raise ValueError(
                f'Inventory XLSX profile {report_type!r} uses unknown overview chart '
                f'category field {chart.category_key!r}.'
            )
        if chart.aggregation == 'count':
            if chart.value_key is not None:
                raise ValueError(
                    f'Inventory XLSX profile {report_type!r} count chart must not declare a value field.'
                )
            continue
        if chart.aggregation != 'value' or chart.value_key is None:
            raise ValueError(
                f'Inventory XLSX profile {report_type!r} has unsupported overview chart aggregation '
                f'{chart.aggregation!r}.'
            )
        value_column = columns.get(chart.value_key)
        if value_column is None:
            raise ValueError(
                f'Inventory XLSX profile {report_type!r} uses unknown overview chart '
                f'value field {chart.value_key!r}.'
            )
        if value_column.data_type not in numeric_types:
            raise ValueError(
                f'Inventory XLSX profile {report_type!r} overview chart value field '
                f'{chart.value_key!r} must be numeric.'
            )


_validate_inventory_workbook_profiles()

INVENTORY_XLSX_REPORT_TYPES = frozenset(INVENTORY_WORKBOOK_PROFILES)


def get_inventory_workbook_profile(report_type: str) -> InventoryWorkbookProfile:
    try:
        return INVENTORY_WORKBOOK_PROFILES[report_type]
    except KeyError as exc:
        raise ValueError(f'Unsupported Inventory Excel report type: {report_type}.') from exc
