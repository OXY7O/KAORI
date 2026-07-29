from __future__ import annotations

from typing import Any

from app.analytics.top_consumers.service import TopConsumersService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_top_consumers_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService

def get_report_top_consumers_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Top Consumers report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        top_consumers_service = TopConsumersService(
            utilization_service,
        )

        prometheus_status = top_consumers_service.get_prometheus_status()

        selected_namespace = report.namespace or ''
        namespace_options = top_consumers_service.get_namespace_options()

        consumer_payload = top_consumers_service.get_top_consumers_payload(
            selected_namespace=selected_namespace,
            selected_resource='all',
            selected_search='',
            selected_sort='usage_percent',
            selected_focus='',
            page=1,
            per_page=1000,
        )

        actionable_recommendations = build_top_consumers_actionable_recommendations(
            consumer_payload,
        )
        consumer_payload = {
            **consumer_payload,
            'actionable_recommendations': actionable_recommendations,
        }

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
            'selected_namespace': selected_namespace or 'All Namespaces',
            'selected_time_range': report.period or '24h',
            'prometheus_status': prometheus_status,
            'namespace_options': namespace_options,
            'consumer_payload': consumer_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }
