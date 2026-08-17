from __future__ import annotations

from typing import Any

from app.analytics.kubernetes.capacity.service import CapacityService
from app.analytics.kubernetes.utilization.service import UtilizationService
from app.cluster.constants import get_environment_label
from app.metrics.consumer import MetricsConsumer
from app.metrics.service import MetricsService
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_capacity_analysis_payload(
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

        capacity_service = CapacityService(
            utilization_service,
            MetricsConsumer(cluster),
        )

        metrics_source_status = utilization_service.get_metrics_source_status()

        report_period = report.period or '24h'
        capacity_payload = capacity_service.get_capacity_analysis(
            time_range=report_period,
        )
        forecast_payload = _collect_forecast(
            cluster=cluster,
            namespace=report.namespace or '',
            period=report_period,
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
            'metrics_source_status': metrics_source_status,
            'forecast_payload': forecast_payload,
            'source_evidence': _source_evidence(
                metrics_source_status=metrics_source_status,
                report_period=report_period,
                forecast_payload=forecast_payload,
            ),
            **capacity_payload,
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)


def _collect_forecast(
    *,
    cluster: Any,
    namespace: str,
    period: str,
) -> dict[str, Any]:
    try:
        from app.analytics.kubernetes.materialization.service import read_snapshot

        result = read_snapshot(
            cluster_id=str(getattr(cluster, 'id', '')),
            dataset_key='analytics.forecast',
            parameters={
                'cluster_id': str(getattr(cluster, 'id', '')),
                'history_window': _forecast_history_window(period),
                'namespace': namespace,
            },
        )
        context = result.context or {}
        forecast_payload = context.get('forecast_payload')
        return forecast_payload if isinstance(forecast_payload, dict) else {}
    except Exception:
        # Capacity posture remains reportable when optional committed forecast
        # evidence is unavailable. The publication renders an explicit state.
        return {}


def _forecast_history_window(period: str) -> str:
    if period in {'7d', '30d', '90d'}:
        return period
    if period == '60d':
        return '90d'
    return '7d'


def _source_evidence(
    *,
    metrics_source_status: dict[str, Any],
    report_period: str,
    forecast_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            'source': 'Metrics Source Observation Cache',
            'freshness': _format_latency(metrics_source_status.get('response_time_ms')),
            'last_collected': metrics_source_status.get('last_checked_at') or 'Not Available',
        },
        {
            'source': 'Kubernetes Cluster Scope',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Capacity Analysis Evidence',
            'freshness': report_period,
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Forecast Evidence',
            'freshness': forecast_payload.get('forecast_horizon') or 'Not Available',
            'last_collected': forecast_payload.get('generated_at') or 'Not Available',
        },
    ]


def _format_latency(value: Any) -> str:
    try:
        return f'{float(value):.0f} ms'
    except (TypeError, ValueError):
        return 'Not Available'
