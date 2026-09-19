from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models.report import Report
from app.reports.catalog import ANALYTICS_REPORT_TYPES, validate_report_instance
from app.reports.export.payloads.alerts import get_report_alerts_anomalies_payload
from app.reports.export.payloads.analytics import get_report_analytics_overview_payload
from app.reports.export.payloads.capacity import get_report_capacity_analysis_payload
from app.reports.export.payloads.forecast import get_report_resource_forecast_payload
from app.reports.export.payloads.object_storage_analysis import get_report_object_storage_analysis_payload
from app.reports.export.payloads.storage import get_report_storage_analysis_payload
from app.reports.export.payloads.top_consumers import get_report_top_consumers_payload
from app.reports.export.payloads.utilization import get_report_resource_utilization_payload
from app.reports.export.payloads.workload import get_report_workload_analysis_payload

PayloadCollector = Callable[[Report], dict[str, Any]]

_PAYLOAD_COLLECTORS: dict[str, PayloadCollector] = {
    'analytics_overview': get_report_analytics_overview_payload,
    'resource_utilization': get_report_resource_utilization_payload,
    'capacity_analysis': get_report_capacity_analysis_payload,
    'storage_analysis': get_report_storage_analysis_payload,
    'workload_analysis': get_report_workload_analysis_payload,
    'resource_forecast': get_report_resource_forecast_payload,
    'top_consumers': get_report_top_consumers_payload,
    'alerts_anomalies': get_report_alerts_anomalies_payload,
    'object_storage_analysis': get_report_object_storage_analysis_payload,
}


def collect_report_payload(report: Report) -> dict[str, Any]:
    """Collect analytics data through the canonical selected-cluster contract."""

    validate_report_instance(report)
    if report.report_type not in ANALYTICS_REPORT_TYPES:
        raise ValueError(f'HTML/PDF analytics collector does not support report type {report.report_type!r}.')

    collector = _PAYLOAD_COLLECTORS.get(report.report_type)
    if collector is None:
        raise ValueError(f'No analytics data collector is registered for {report.report_type!r}.')
    return collector(report)
