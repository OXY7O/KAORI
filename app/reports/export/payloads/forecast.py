from __future__ import annotations

from typing import Any

from app.analytics.kubernetes.forecast.presentation import present_forecast_materialized_context
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_resource_forecast_payload(report: Report) -> dict[str, Any]:
    """Build the Resource Forecast report from committed materialized evidence.

    PDF generation must not issue long-range Metrics Source queries. The selected
    history snapshot is loaded from ``analytics.forecast`` and re-projected in
    memory for the configured horizon and Holt-Winters method.
    """
    cluster = None
    try:
        cluster = get_report_selected_cluster(report)

        history_window = normalize_report_forecast_history_window(report.period or '30d')
        forecast_horizon = normalize_report_forecast_horizon(report.period or '90d')
        namespace = report.namespace or ''
        context, snapshot_collected_at = _read_committed_context(
            cluster_id=str(getattr(cluster, 'id', '')),
            namespace=namespace,
            history_window=history_window,
        )

        if context:
            presented = present_forecast_materialized_context(
                context,
                {
                    'namespace': namespace,
                    'history_window': history_window,
                    'forecast_horizon': forecast_horizon,
                    'method': 'holt_winters',
                    'tab': 'trend',
                },
            )
            forecast_payload = presented.get('forecast_payload')
            if not isinstance(forecast_payload, dict):
                forecast_payload = {}
            namespace_options = list(presented.get('namespace_options') or [])
        else:
            forecast_payload = _unavailable_forecast_payload(
                namespace=namespace,
                history_window=history_window,
                forecast_horizon=forecast_horizon,
            )
            namespace_options = []

        return {
            'cluster': {
                'id': str(getattr(cluster, 'id', '')),
                'name': str(getattr(cluster, 'name', 'Unknown Cluster')),
                'environment': get_environment_label(
                    getattr(cluster, 'environment', None),
                    empty='',
                ),
                'status': str(getattr(cluster, 'status', '') or ''),
            },
            'selected_namespace': namespace or 'All Namespaces',
            'history_window': history_window,
            'forecast_horizon': forecast_horizon,
            'namespace_options': namespace_options,
            'forecast_payload': forecast_payload,
            'source_evidence': _source_evidence(
                history_window=history_window,
                forecast_horizon=forecast_horizon,
                generated_at=forecast_payload.get('generated_at') or snapshot_collected_at,
                available=bool(context),
            ),
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)


def _read_committed_context(
    *,
    cluster_id: str,
    namespace: str,
    history_window: str,
) -> tuple[dict[str, Any], Any]:
    try:
        from app.analytics.kubernetes.materialization.service import read_snapshot

        result = read_snapshot(
            cluster_id=cluster_id,
            dataset_key='analytics.forecast',
            parameters={
                'cluster_id': cluster_id,
                'history_window': history_window,
                'namespace': namespace,
            },
        )
        context = result.context or {}
        if not isinstance(context, dict):
            return {}, None
        snapshot = getattr(result, 'snapshot', None)
        collected_at = getattr(snapshot, 'generated_at', None)
        return context, collected_at
    except Exception:
        # Missing or stale committed evidence is a reportable state. The PDF is
        # still generated with explicit Not Available values.
        return {}, None


def _unavailable_forecast_payload(
    *,
    namespace: str,
    history_window: str,
    forecast_horizon: str,
) -> dict[str, Any]:
    return {
        'has_data': False,
        'message': 'Committed forecast evidence is not available for the selected reporting boundary.',
        'namespace': namespace,
        'history_window': history_window,
        'forecast_horizon': forecast_horizon,
        'forecast_method': 'holt_winters',
        'method_label': 'Holt-Winters',
        'generated_at': None,
        'items': [],
        'summary': {
            'total_resources': 4,
            'forecasted_resources': 0,
            'unavailable_resources': 4,
            'warning_count': 0,
            'critical_count': 0,
            'highest_projected_label': 'N/A',
            'highest_projected_percent': None,
            'nearest_warning': {'resource': None, 'label': 'Not projected', 'days': None, 'date': None},
            'nearest_critical': {'resource': None, 'label': 'Not projected', 'days': None, 'date': None},
        },
        'actionable_recommendations': [],
        'recommendation_cards': [],
        'recommendation_count': 0,
    }


def _source_evidence(
    *,
    history_window: str,
    forecast_horizon: str,
    generated_at: Any,
    available: bool,
) -> list[dict[str, Any]]:
    state = 'Committed' if available else 'Not Available'
    collected = generated_at or 'Not Available'
    return [
        {
            'source': 'Forecast Materialized Snapshot',
            'freshness': history_window if available else state,
            'last_collected': collected,
        },
        {
            'source': 'Forecast Projection Evidence',
            'freshness': forecast_horizon if available else state,
            'last_collected': collected,
        },
        {
            'source': 'Threshold Policy',
            'freshness': '75% / 90%',
            'last_collected': 'Configuration',
        },
    ]


def normalize_report_forecast_history_window(value: str) -> str:
    if value in {'7d', '30d', '90d'}:
        return value
    if value in {'1h', '6h', '12h', '24h'}:
        return '7d'
    if value == '60d':
        return '90d'
    return '30d'


def normalize_report_forecast_horizon(value: str) -> str:
    if value in {'7d', '30d', '90d', '180d', '365d'}:
        return value
    return '90d'
