from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models.report import Report
from app.reports.export.payloads.alerts import get_report_alerts_anomalies_payload
from app.reports.export.payloads.analytics import get_report_analytics_overview_payload
from app.reports.export.payloads.capacity import get_report_capacity_analysis_payload
from app.reports.export.payloads.forecast import get_report_resource_forecast_payload
from app.reports.export.payloads.inventory import get_report_kubernetes_inventory_payload
from app.reports.export.payloads.storage import get_report_storage_analysis_payload
from app.reports.export.payloads.top_consumers import get_report_top_consumers_payload
from app.reports.export.payloads.tls_certificate_health import get_report_tls_certificate_health_payload
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
    'tls_certificate_health': get_report_tls_certificate_health_payload,
    'inventory_overview': get_report_kubernetes_inventory_payload,
    'node_inventory': get_report_kubernetes_inventory_payload,
    'namespace_inventory': get_report_kubernetes_inventory_payload,
    'workload_inventory': get_report_kubernetes_inventory_payload,
    'pod_inventory': get_report_kubernetes_inventory_payload,
    'service_inventory': get_report_kubernetes_inventory_payload,
    'ingress_inventory': get_report_kubernetes_inventory_payload,
    'storage_inventory': get_report_kubernetes_inventory_payload,
    'topology_inventory': get_report_kubernetes_inventory_payload,
}


def collect_report_payload(report: Report) -> dict[str, Any]:
    collector = _PAYLOAD_COLLECTORS.get(report.report_type)
    if collector is None:
        return {
            '_error': 'This report type does not have a data collector yet.',
        }
    return collector(report)
