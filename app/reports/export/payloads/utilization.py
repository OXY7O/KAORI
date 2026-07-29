from __future__ import annotations

from typing import Any

from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.prometheus.service import PrometheusService

def get_report_resource_utilization_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Resource Utilization report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        service = UtilizationService(
            prometheus,
        )

        prometheus_status = service.get_prometheus_status()
        summary = service.get_summary()
        summary_table = service.get_summary_table(
            summary,
        )
        cluster_info = service.get_cluster_info(
            summary,
        )
        risk_assessment = service.get_capacity_pressure_risk(
            summary,
        )
        top_cpu_consumers = service.get_top_cpu_consumers()
        top_memory_consumers = service.get_top_memory_consumers()

        return {
            'cluster': {
                'id': str(
                    getattr(
                        cluster,
                        'id',
                        '',
                    )
                ),
                'name': str(
                    getattr(
                        cluster,
                        'name',
                        'Unknown Cluster',
                    )
                ),
                'environment': get_environment_label(getattr(cluster, 'environment', None), empty=''),
                'status': str(
                    getattr(
                        cluster,
                        'status',
                        '',
                    )
                    or ''
                ),
            },
            'prometheus_status': prometheus_status,
            'summary': summary,
            'summary_table': summary_table,
            'cluster_info': cluster_info,
            'risk_assessment': risk_assessment,
            'top_cpu_consumers': top_cpu_consumers[:5],
            'top_memory_consumers': top_memory_consumers[:5],
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }
