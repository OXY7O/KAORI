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

INVENTORY_XLSX_REPORT_TYPES = frozenset(INVENTORY_WORKBOOK_PROFILES)


def get_inventory_workbook_profile(report_type: str) -> InventoryWorkbookProfile:
    try:
        return INVENTORY_WORKBOOK_PROFILES[report_type]
    except KeyError as exc:
        raise ValueError(f'Unsupported Inventory Excel report type: {report_type}.') from exc
