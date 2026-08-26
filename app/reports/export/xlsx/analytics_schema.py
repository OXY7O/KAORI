from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, Mapping

ANALYTICS_WORKBOOK_STANDARD: Final = 'kaori-analytics-xlsx-v1.0'
ANALYTICS_WORKBOOK_FAMILY: Final = 'analytics'
ANALYTICS_OVERVIEW_SHEET: Final = 'Overview'
ANALYTICS_METADATA_SHEET: Final = 'Metadata'
ANALYTICS_DICTIONARY_SHEET: Final = 'Field Dictionary'

AnalyticsVisualType = Literal['line', 'ranked_bar', 'doughnut', 'capacity_bar', 'comparison_bar']
AnalyticsDataType = Literal['text', 'integer', 'number', 'percent', 'datetime', 'date']


@dataclass(frozen=True, slots=True)
class AnalyticsExportContext:
    report_id: int | str
    report_name: str
    report_type: str
    generated_at: datetime
    generated_by: str
    scope_label: str
    scope_value: str
    namespace_scope: str
    period_label: str
    data_cutoff: datetime | date | str | None
    classification: str = 'Internal'


@dataclass(frozen=True, slots=True)
class AnalyticsMetricSpec:
    label: str
    number_format: str = 'General'
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsMetricValue:
    label: str
    value: Any
    number_format: str = 'General'
    unit: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsColumn:
    key: str
    label: str
    definition: str
    data_type: AnalyticsDataType = 'text'
    number_format: str | None = None
    unit: str | None = None
    width: float = 18.0


@dataclass(frozen=True, slots=True)
class AnalyticsTableData:
    sheet_name: str
    title: str
    description: str
    columns: tuple[AnalyticsColumn, ...]
    rows: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class AnalyticsChartSeries:
    key: str
    label: str
    number_format: str = '0.0'
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsChartData:
    title: str
    visual_type: AnalyticsVisualType
    source_sheet: str
    rows: tuple[Mapping[str, Any], ...]
    category_key: str = 'category'
    series: tuple[AnalyticsChartSeries, ...] = ()
    top_n: int = 8
    value_axis_title: str | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsWorkbookProfile:
    report_type: str
    title: str
    description: str
    metric_specs: tuple[AnalyticsMetricSpec, ...]
    sheet_names: tuple[str, ...]
    primary_visual: AnalyticsVisualType


@dataclass(frozen=True, slots=True)
class AnalyticsWorkbookData:
    profile: AnalyticsWorkbookProfile
    context: AnalyticsExportContext
    metrics: tuple[AnalyticsMetricValue, ...]
    readout: str
    tables: tuple[AnalyticsTableData, ...]
    primary_chart: AnalyticsChartData | None

    def table(self, sheet_name: str) -> AnalyticsTableData | None:
        return next((table for table in self.tables if table.sheet_name == sheet_name), None)
