from __future__ import annotations

from typing import Any

from app.analytics.forecast.service import ForecastAnalysisService
from app.analytics.utilization.service import UtilizationService
from app.analytics.utilization.service import (
    get_selected_cluster as get_utilization_selected_cluster,
)
from app.cluster.constants import get_environment_label
from app.intelligence.recommendation_engine import build_forecast_actionable_recommendations
from app.models.report import Report
from app.prometheus.service import PrometheusService

def get_report_resource_forecast_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_utilization_selected_cluster(
            report.cluster_id,
        )

        if not cluster:
            return {
                '_error': 'No cluster configured for Resource Forecast report.',
            }

        prometheus = PrometheusService(
            cluster,
        )

        utilization_service = UtilizationService(
            prometheus,
        )

        prometheus_status = utilization_service.get_prometheus_status()

        forecast_service = ForecastAnalysisService(
            utilization_service=utilization_service,
            cluster=cluster,
        )

        selected_namespace = report.namespace or ''
        history_window = normalize_report_forecast_history_window(
            report.period or '30d',
        )
        forecast_horizon = normalize_report_forecast_horizon(
            report.period or '90d',
        )

        namespace_options = forecast_service.get_namespace_options()

        forecast_payload = forecast_service.get_forecast_analysis(
            namespace=selected_namespace,
            history_window=history_window,
            forecast_horizon=forecast_horizon,
            resource='all',
        )

        actionable_recommendations = build_forecast_actionable_recommendations(
            forecast_payload,
        )

        forecast_payload = {
            **forecast_payload,
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
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'prometheus_status': prometheus_status,
            'namespace_options': namespace_options,
            'forecast_payload': forecast_payload,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def normalize_report_forecast_history_window(
    value: str,
) -> str:
    if value in [
        '7d',
        '30d',
        '90d',
    ]:
        return value

    if value in [
        '1h',
        '6h',
        '24h',
    ]:
        return '7d'

    return '30d'


def normalize_report_forecast_horizon(
    value: str,
) -> str:
    if value in [
        '7d',
        '30d',
        '90d',
        '180d',
        '365d',
    ]:
        return value

    return '90d'
