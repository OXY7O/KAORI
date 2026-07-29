from __future__ import annotations

from typing import Any

from app.analytics.capacity.service import CapacityService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.service import PrometheusService

def get_report_capacity_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Capacity Analysis report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        capacity_service = CapacityService(
            utilization_service,
            PrometheusConsumer(cluster),
        )

        prometheus_status = utilization_service.get_prometheus_status()

        capacity_payload = capacity_service.get_capacity_analysis(
            time_range=report.period or '24h',
        )

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
            **capacity_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }
