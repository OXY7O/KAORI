from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.reports.export.xlsx.analytics_preparation.alerts import prepare_alerts
from app.reports.export.xlsx.analytics_preparation.capacity import prepare_capacity
from app.reports.export.xlsx.analytics_preparation.forecast import prepare_forecast
from app.reports.export.xlsx.analytics_preparation.object_storage import prepare_object_storage
from app.reports.export.xlsx.analytics_preparation.overview import prepare_overview
from app.reports.export.xlsx.analytics_preparation.resource_utilization import prepare_resource_utilization
from app.reports.export.xlsx.analytics_preparation.storage import prepare_storage
from app.reports.export.xlsx.analytics_preparation.tenant_governance import prepare_tenant_governance
from app.reports.export.xlsx.analytics_preparation.top_consumers import prepare_top_consumers
from app.reports.export.xlsx.analytics_preparation.workload import prepare_workload
from app.reports.export.xlsx.analytics_profile_catalog import (
    ANALYTICS_WORKBOOK_PROFILES,
    ANALYTICS_XLSX_REPORT_TYPES,
)
from app.reports.export.xlsx.analytics_schema import (
    AnalyticsExportContext,
    AnalyticsWorkbookData,
    AnalyticsWorkbookProfile,
)


def get_analytics_workbook_profile(report_type: str) -> AnalyticsWorkbookProfile:
    try:
        return ANALYTICS_WORKBOOK_PROFILES[report_type]
    except KeyError as exc:
        raise ValueError(f'Unsupported Analytics Excel report type: {report_type}.') from exc


_Preparer = Callable[[Mapping[str, Any], AnalyticsExportContext, AnalyticsWorkbookProfile], AnalyticsWorkbookData]

_PREPARERS: dict[str, _Preparer] = {
    'analytics_overview': prepare_overview,
    'resource_utilization': prepare_resource_utilization,
    'capacity_analysis': prepare_capacity,
    'storage_analysis': prepare_storage,
    'workload_analysis': prepare_workload,
    'resource_forecast': prepare_forecast,
    'top_consumers': prepare_top_consumers,
    'alerts_anomalies': prepare_alerts,
    'tenant_governance': prepare_tenant_governance,
    'object_storage_analysis': prepare_object_storage,
}


def prepare_analytics_workbook_data(
    report_type: str,
    payload: Mapping[str, Any],
    context: AnalyticsExportContext,
) -> AnalyticsWorkbookData:
    if context.report_type != report_type:
        raise ValueError('Analytics export context does not match the requested report type.')
    profile = get_analytics_workbook_profile(report_type)
    return _PREPARERS[report_type](payload, context, profile)


__all__ = [
    'ANALYTICS_WORKBOOK_PROFILES',
    'ANALYTICS_XLSX_REPORT_TYPES',
    'get_analytics_workbook_profile',
    'prepare_analytics_workbook_data',
]
