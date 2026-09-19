from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypedDict, Unpack

XLSX_REPORTING_STANDARD: Final = 'kaori-reporting-xlsx-v2.0'
INVENTORY_WORKBOOK_STANDARD: Final = 'kaori-inventory-xlsx-v4.0'
INVENTORY_WORKBOOK_FAMILY: Final = 'inventory'
INVENTORY_OVERVIEW_SHEET: Final = 'Overview'
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
    source_key: str | None = None
    scale_divisor: float | None = None
    ratio_numerator_key: str | None = None
    ratio_denominator_key: str | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryOverviewMetric:
    label: str
    aggregation: Literal[
        'row_count',
        'count',
        'sum',
        'distinct_count',
        'coverage_percent',
        'leading_share',
    ]
    key: str | None = None
    match_values: tuple[str | bool, ...] = ()
    exclude_values: tuple[str | bool, ...] = ()
    number_format: str = '#,##0'
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class InventoryOverviewChart:
    title: str
    category_key: str
    visual_type: Literal['ranked_bar', 'doughnut']
    aggregation: Literal['count', 'value'] = 'count'
    value_key: str | None = None
    top_n: int = 8


@dataclass(frozen=True, slots=True)
class InventoryWorkbookProfile:
    report_type: str
    title: str
    description: str
    columns: tuple[InventoryColumn, ...]
    overview_metrics: tuple[InventoryOverviewMetric, ...]
    overview_chart: InventoryOverviewChart
    record_label: str = 'records'
    row_source: str = 'inventory_assets'
    identity_columns: tuple[str, ...] = ()


class InventoryColumnOptions(TypedDict, total=False):
    data_type: str
    source: str
    missing_value_rule: str
    width: float
    number_format: str | None
    semantic_type: str | None
    source_key: str | None
    scale_divisor: float | None
    ratio_numerator_key: str | None
    ratio_denominator_key: str | None
    unit: str | None


def column(
    key: str,
    label: str,
    definition: str,
    **options: Unpack[InventoryColumnOptions],
) -> InventoryColumn:
    return InventoryColumn(
        key=key,
        label=label,
        definition=definition,
        **options,
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
