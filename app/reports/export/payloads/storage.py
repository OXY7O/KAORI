from __future__ import annotations

from typing import Any

from app.analytics.storage.service import StorageAnalysisService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.service import PrometheusService

def get_report_storage_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Storage Analysis report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        storage_service = StorageAnalysisService(
            utilization_service,
            PrometheusConsumer(cluster),
        )

        prometheus_status = storage_service.get_prometheus_status()

        storage_summary = storage_service.get_storage_capacity_summary(
            selected_namespace=report.namespace or '',
            selected_node='',
            selected_pvc_search='',
            selected_pvc_status='',
            selected_pvc_storage_class='',
            pvc_page=1,
            pvc_per_page=1000,
            selected_pv_search='',
            selected_pv_status='',
            selected_pv_storage_class='',
            pv_page=1,
            pv_per_page=1000,
        )

        namespace_options = storage_service.get_storage_namespace_options()

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
            'selected_namespace': report.namespace or 'All Namespaces',
            'selected_time_range': report.period or '24h',
            'prometheus_status': prometheus_status,
            'storage_summary': storage_summary,
            'namespace_options': namespace_options,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }
