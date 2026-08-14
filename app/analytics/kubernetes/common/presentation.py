from __future__ import annotations

from datetime import datetime
from typing import Any

PROMETHEUS_STATUS_SCHEMA_VERSION = 1


def present_prometheus_status(status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the canonical Prometheus readiness payload used by Analytics UI.

    The source services historically emitted slightly different labels, messages,
    timestamps, and readiness keys.  The presentation contract intentionally
    collapses those differences so every Kubernetes Analytics page renders the
    same status, response latency, and observation timestamp semantics.
    """
    source = dict(status or {})
    raw_label = str(source.get('status_label') or source.get('label') or source.get('status') or '').strip()
    raw_label_lower = raw_label.lower().replace('_', ' ')
    connected = bool(source.get('connected', source.get('success', False)))
    observation_degraded = bool(source.get('observation_degraded'))
    waiting_for_cluster = 'waiting' in raw_label_lower or ('cluster' in raw_label_lower and 'select' in raw_label_lower)

    configured_value = source.get('configured')
    if configured_value is None:
        configured = not (waiting_for_cluster or 'not configured' in raw_label_lower)
    else:
        configured = bool(configured_value)

    if waiting_for_cluster:
        state = 'waiting_for_cluster'
        status_label = 'Waiting for Cluster'
        tone = 'disabled'
        icon = 'circle-dashed'
        message = 'Select or register a Kubernetes cluster before Prometheus readiness can be evaluated.'
    elif not configured:
        state = 'not_configured'
        status_label = 'Not Configured'
        tone = 'unknown'
        icon = 'settings'
        message = 'Configure and bind a Prometheus-compatible source for the selected cluster.'
    elif connected and observation_degraded:
        state = 'query_degraded'
        status_label = 'Query Degraded'
        tone = 'warning'
        icon = 'triangle-alert'
        message = 'Prometheus can execute analytics queries, but the latest runtime observation is degraded.'
    elif connected:
        state = 'query_ready'
        status_label = 'Query Ready'
        tone = 'normal'
        icon = 'circle-check'
        message = 'Prometheus is reachable and eligible for Kubernetes Analytics queries.'
    else:
        state = 'unavailable'
        status_label = 'Unavailable'
        tone = 'critical'
        icon = 'circle-x'
        message = 'Prometheus cannot execute Kubernetes Analytics queries for the selected cluster.'

    response_time_ms = source.get('response_time_ms')
    try:
        response_time_ms = int(round(float(response_time_ms))) if response_time_ms is not None else None
    except (TypeError, ValueError):
        response_time_ms = None

    error = source.get('error') or source.get('last_error')
    if state == 'unavailable' and error:
        detail = str(error).strip()
        if detail:
            message = detail

    return {
        **source,
        'schema_version': PROMETHEUS_STATUS_SCHEMA_VERSION,
        'configured': configured,
        'connected': connected,
        'observation_degraded': observation_degraded,
        'state': state,
        'status': state,
        'status_label': status_label,
        'label': status_label,
        'tone': tone,
        'status_tone': tone,
        'icon': icon,
        'message': message,
        'description': message,
        'response_time_ms': response_time_ms,
        'response_time_display': f'{response_time_ms} ms' if response_time_ms is not None else 'No Response',
        'last_checked_at': source.get('last_checked_at') or source.get('checked_at'),
        'error': error,
    }


def percent_display(value: Any, *, digits: int = 1) -> str:
    try:
        return f'{float(value or 0):.{digits}f}%'
    except (TypeError, ValueError):
        return '0.0%'


def gib_display(value_bytes: Any, *, digits: int = 2) -> str:
    try:
        return f'{float(value_bytes or 0) / (1024**3):.{digits}f} GiB'
    except (TypeError, ValueError):
        return '0.00 GiB'


def datetime_display(value: datetime | None, *, fallback: str = 'Not recorded') -> str:
    if value is None:
        return fallback
    return value.strftime('%d %b %Y, %H:%M %Z').strip()


def present_utilization_context(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    cluster_info = result.get('cluster_info')
    if cluster_info is not None:
        setattr(cluster_info, 'memory_capacity_display', gib_display(getattr(cluster_info, 'memory_capacity', 0)))
    summary = result.get('summary')
    if summary is not None:
        usage = gib_display(getattr(summary, 'memory_usage', 0))
        capacity = gib_display(getattr(summary, 'memory_capacity', 0))
        setattr(summary, 'memory_detail_display', f'{usage} / {capacity}')
    result['ready_ratio_display'] = percent_display(result.get('ready_ratio'), digits=0)
    detail = result.get('detail_summary')
    if detail is not None:
        usage = gib_display(getattr(detail, 'memory_usage', 0))
        capacity = gib_display(getattr(detail, 'memory_capacity', 0))
        setattr(detail, 'memory_detail_display', f'{usage} / {capacity}')
    return result
