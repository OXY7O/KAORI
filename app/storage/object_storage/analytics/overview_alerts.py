from __future__ import annotations

from typing import Any

from app.storage.object_storage.analytics.alert_sources import build_alert_posture, resolve_materialized_alert_stream


def _anomaly_tone(signals: list[dict[str, Any]]) -> str:
    severities = {str(item.get('severity') or '').strip().lower() for item in signals}
    if 'critical' in severities:
        return 'critical'
    if 'warning' in severities:
        return 'warning'
    if 'normal' in severities:
        return 'normal'
    return 'unknown'


def build_overview_alert_summary(
    *,
    payload: dict[str, Any],
    selected_source: str,
) -> dict[str, Any]:
    """Project committed provider-alert and anomaly evidence into Overview.

    This is an Analytics summary only. It never reads Alert Intelligence cases
    or durable Intelligence recommendations.
    """

    streams = payload.get('alert_streams') if isinstance(payload.get('alert_streams'), dict) else {}
    stream = resolve_materialized_alert_stream(streams, selected_source=selected_source)
    posture = build_alert_posture(stream)

    page_metrics = payload.get('page_metrics') if isinstance(payload.get('page_metrics'), dict) else {}
    alerts_metrics = page_metrics.get('alerts') if isinstance(page_metrics.get('alerts'), dict) else {}
    signals = [item for item in alerts_metrics.get('signals') or [] if isinstance(item, dict)]
    actionable_signals = [
        item for item in signals if str(item.get('severity') or '').strip().lower() in {'critical', 'warning'}
    ]

    metrics_source = payload.get('metrics_source') if isinstance(payload.get('metrics_source'), dict) else {}
    metrics_runtime_state = str(metrics_source.get('runtime_state') or '').strip().lower()
    metrics_operational = metrics_runtime_state in {'operational', 'degraded'}
    provider_operational = bool(stream.get('connected'))

    return {
        'source': stream,
        'posture': posture,
        'provider_alert_count': int(posture.get('total') or 0),
        'critical_count': int(posture.get('critical') or 0),
        'warning_count': int(posture.get('warning') or 0),
        'anomaly_count': len(actionable_signals),
        'anomaly_tone': _anomaly_tone(signals),
        'signals': signals,
        'evidence_available': provider_operational or metrics_operational,
        'degraded': not (provider_operational and metrics_operational),
    }
