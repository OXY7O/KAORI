from __future__ import annotations

from dataclasses import dataclass
from typing import Final

INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v2.0'
INVENTORY_WORKBOOK_FAMILY: Final = 'inventory'
INVENTORY_DATA_SHEET: Final = 'Inventory'
INVENTORY_METADATA_SHEET: Final = 'Metadata'
INVENTORY_DICTIONARY_SHEET: Final = 'Field Dictionary'


@dataclass(frozen=True, slots=True)
class InventoryColumn:
    key: str
    label: str
    definition: str
    data_type: str = 'text'
    source: str = 'Committed inventory snapshot'
    missing_value_rule: str = 'Not Available'
    width: float = 18.0
    number_format: str | None = None
    semantic_type: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryWorkbookProfile:
    report_type: str
    title: str
    description: str
    columns: tuple[InventoryColumn, ...]
    row_source: str = 'inventory_assets'
    identity_columns: tuple[str, ...] = ()


def column(
    key: str,
    label: str,
    definition: str,
    *,
    data_type: str = 'text',
    source: str = 'Committed inventory snapshot',
    missing_value_rule: str = 'Not Available',
    width: float = 18.0,
    number_format: str | None = None,
    semantic_type: str | None = None,
) -> InventoryColumn:
    return InventoryColumn(
        key=key,
        label=label,
        definition=definition,
        data_type=data_type,
        source=source,
        missing_value_rule=missing_value_rule,
        width=width,
        number_format=number_format,
        semantic_type=semantic_type,
    )


CREATED_AT_COLUMN = column(
    'created_at',
    'Created At',
    'Kubernetes resource creation timestamp when present.',
    data_type='datetime',
    missing_value_rule='Not Available',
    width=20,
    number_format='yyyy-mm-dd hh:mm',
)

COLLECTED_AT_COLUMN = column(
    'collected_at',
    'Last Collected',
    'Timestamp of the committed inventory row.',
    data_type='datetime',
    missing_value_rule='Not Available',
    width=20,
    number_format='yyyy-mm-dd hh:mm',
)
