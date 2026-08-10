from __future__ import annotations

from typing import Any

from app.analytics.utilization.service import UtilizationService
from app.cluster.constants import get_environment_label
from app.models.report import Report
from app.prometheus.service import PrometheusService
from app.reports.export.payloads.common import get_report_selected_cluster, report_payload_error


def get_report_resource_utilization_payload(
    report: Report,
) -> dict[str, Any]:
    cluster = None
    try:
        cluster = get_report_selected_cluster(report)

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
        top_memory_consumers = _normalize_memory_consumers(service.get_top_memory_consumers())

        trend_hours, trend_step = _resolve_trend_window(report.period or '24h')
        trends = _collect_trends(
            service,
            hours=trend_hours,
            step=trend_step,
        )
        forecast_payload = _collect_forecast(
            cluster=cluster,
            namespace=report.namespace or '',
            period=report.period or '30d',
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
            'prometheus_status': prometheus_status,
            'summary': summary,
            'summary_table': summary_table,
            'cluster_info': cluster_info,
            'risk_assessment': risk_assessment,
            'top_cpu_consumers': top_cpu_consumers[:5],
            'top_memory_consumers': top_memory_consumers[:5],
            'trends': trends,
            'trend_window': {
                'hours': trend_hours,
                'step': trend_step,
                'period': report.period or '24h',
            },
            'forecast_payload': forecast_payload,
            'source_evidence': _source_evidence(
                prometheus_status=prometheus_status,
                report_period=report.period or '24h',
                forecast_payload=forecast_payload,
            ),
        }
    except Exception as exc:
        return report_payload_error(exc, cluster=cluster)


_BYTES_PER_GIB = 1024**3


def _normalize_memory_consumers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add an explicit GiB value while preserving the Prometheus byte evidence."""
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        row = dict(item)
        try:
            value_bytes = max(0.0, float(item.get('value') or 0.0))
        except (TypeError, ValueError):
            value_bytes = 0.0

        row['value_bytes'] = value_bytes
        row['value_gib'] = value_bytes / _BYTES_PER_GIB
        row['unit'] = 'GiB'
        normalized.append(row)

    return normalized


def _collect_trends(
    service: UtilizationService,
    *,
    hours: int,
    step: str,
) -> dict[str, list[dict[str, float]]]:
    try:
        return service.get_trends(
            hours=hours,
            step=step,
        )
    except Exception:
        # Current utilization remains valid when optional historical evidence is unavailable.
        return {}


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
        # Forecast evidence is optional for this report. The template renders an
        # explicit unavailable state instead of blocking the committed snapshot.
        return {}


def _resolve_trend_window(period: str) -> tuple[int, str]:
    windows = {
        '1h': (1, '1m'),
        '6h': (6, '5m'),
        '12h': (12, '10m'),
        '24h': (24, '15m'),
        '7d': (24 * 7, '1h'),
        '30d': (24 * 30, '6h'),
        '60d': (24 * 60, '12h'),
        '90d': (24 * 90, '12h'),
    }
    return windows.get(period, windows['24h'])


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
) -> list[dict[str, Any]]:
    return [
        {
            'source': 'Prometheus Observation Cache',
            'freshness': _format_latency(prometheus_status.get('response_time_ms')),
            'last_collected': prometheus_status.get('last_checked_at') or 'Not Available',
        },
        {
            'source': 'Kubernetes Cluster Scope',
            'freshness': 'Committed',
            'last_collected': 'At report cut-off',
        },
        {
            'source': 'Utilization Trend Evidence',
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
