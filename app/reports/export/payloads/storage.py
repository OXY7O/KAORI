from __future__ import annotations

from typing import Any

from app.analytics.storage.service import (
    StorageAnalysisService,
    build_storage_recommendation_context,
)
from app.analytics.utilization.service import UtilizationService
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.service import PrometheusService


def get_report_storage_analysis_payload(
    report: Report,
) -> dict[str, Any]:
    try:
        cluster = get_report_selected_cluster(report)

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
        utilization_summary = utilization_service.get_summary()
        cluster_info = utilization_service.get_cluster_info(
            utilization_summary,
        )

        storage_summary = storage_service.get_storage_capacity_summary(
            selected_namespace=report.namespace or '',
            selected_node='',
            filesystem_page=1,
            filesystem_per_page=1000,
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
        report_period = report.period or '24h'
        forecast_payload = _collect_forecast(
            cluster=cluster,
            namespace=report.namespace or '',
            period=report_period,
        )
        recommendation_context = build_storage_recommendation_context(
            storage_summary,
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
            'selected_namespace': report.namespace or 'All Namespaces',
            'selected_time_range': report_period,
            'prometheus_status': prometheus_status,
            'cluster_info': cluster_info,
            'storage_summary': storage_summary,
            'namespace_options': namespace_options,
            'forecast_payload': forecast_payload,
            'source_evidence': _source_evidence(
                prometheus_status=prometheus_status,
                report_period=report_period,
                forecast_payload=forecast_payload,
                storage_summary=storage_summary,
            ),
            **recommendation_context,
        }

    except Exception as exc:
        return {
            '_error': str(
                exc,
            ),
        }


def _collect_forecast(
    *,
    cluster: Any,
    namespace: str,
    period: str,
) -> dict[str, Any]:
    try:
        from app.analytics.materialization.service import read_snapshot

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
        # Storage posture remains reportable when optional committed forecast
        # evidence is unavailable. The PDF renders an explicit evidence state.
        return {}


def _forecast_history_window(period: str) -> str:
    if period in {'7d', '30d', '90d'}:
        return period
    if period == '60d':
        return '90d'
    return '7d'


def _source_evidence(
    *,
    prometheus_status: dict[str, Any],
    report_period: str,
    forecast_payload: dict[str, Any],
    storage_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    node_filesystem = storage_summary.get('node_filesystem')
    persistent_storage = storage_summary.get('persistent_storage')
    node_filesystem = node_filesystem if isinstance(node_filesystem, dict) else {}
    persistent_storage = persistent_storage if isinstance(persistent_storage, dict) else {}
    filesystem_summary = node_filesystem.get('summary')
    filesystem_summary = filesystem_summary if isinstance(filesystem_summary, dict) else {}
    pv_summary = persistent_storage.get('pv')
    pvc_summary = persistent_storage.get('pvc')
    pv_summary = pv_summary if isinstance(pv_summary, dict) else {}
    pvc_summary = pvc_summary if isinstance(pvc_summary, dict) else {}

    storage_state = 'Committed' if filesystem_summary.get('evidence_available') else 'Partial'
    inventory_state = 'Committed' if pv_summary.get('evidence_available') or pvc_summary.get('count') else 'Partial'

    return [
        {
            'source': 'Prometheus Observation Cache',
            'freshness': _format_latency(prometheus_status.get('response_time_ms')),
            'last_collected': prometheus_status.get('last_checked_at') or 'Not Available',
        },
        {
            'source': 'Aggregate Storage Capacity',
            'freshness': storage_state,
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Kubernetes Storage Inventory',
            'freshness': inventory_state,
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
