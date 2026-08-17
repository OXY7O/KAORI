from __future__ import annotations

from typing import Any

from app.analytics.kubernetes.top_consumers.contracts import TopConsumersSelection
from app.analytics.kubernetes.top_consumers.service import TopConsumersService
from app.analytics.kubernetes.utilization.service import UtilizationService
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.metrics.service import MetricsService
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_top_consumers_payload(
    report: Report,
) -> dict[str, Any]:
    cluster = None
    try:
        cluster = get_report_selected_cluster(report)

        metrics_source = MetricsService(
            cluster,
        )

        utilization_service = UtilizationService(
            metrics_source,
        )

        top_consumers_service = TopConsumersService(
            utilization_service,
        )

        metrics_source_status = top_consumers_service.get_metrics_source_status()

        selected_namespace = report.namespace or ''
        consumer_payload = top_consumers_service.get_top_consumers_payload(
            TopConsumersSelection(
                namespace=selected_namespace,
                resource='all',
                sort='priority',
                page=1,
                per_page=1000,
            )
        )

        namespace_options = list(consumer_payload.get('namespace_options') or [])
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
                'environment': get_environment_label(
                    getattr(cluster, 'environment', None),
                    empty='',
                ),
                'status': str(
                    getattr(
                        cluster,
                        'status',
                        '',
                    )
                    or ''
                ),
            },
            'selected_namespace': selected_namespace or 'All Namespaces',
            'selected_time_range': 'current',
            'metrics_source_status': metrics_source_status,
            'namespace_options': namespace_options,
            'consumer_payload': consumer_payload,
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)
