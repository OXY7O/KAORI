from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text


@dataclass(frozen=True, slots=True)
class UtilizationState:
    payload: Mapping[str, Any]
    summary: Mapping[str, Any]
    cluster: Mapping[str, Any]
    metrics_source_status: Mapping[str, Any]
    forecast_payload: Mapping[str, Any]
    cpu: dict[str, Any]
    memory: dict[str, Any]
    storage: dict[str, Any]
    pods: dict[str, Any]
    total_nodes: int
    ready_nodes: int
    not_ready_nodes: int
    node_participation: float
    cpu_consumers: list[dict[str, Any]]
    memory_consumers: list[dict[str, Any]]
    forecast_items: dict[str, Mapping[str, Any]]
    cpu_forecast: Mapping[str, Any]
    memory_forecast: Mapping[str, Any]
    pod_forecast: Mapping[str, Any]
    cpu_history: list[float]
    memory_history: list[float]
    pod_history: list[float]
    cpu_projection: float | None
    memory_projection: float | None
    pod_projection: float | None


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def percent(value: float) -> str:
    return f'{max(0.0, min(100.0, value)):.1f}%'


def optional_percent(value: float | None) -> str:
    return percent(value) if value is not None else 'Not Available'


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def consumer_value(items: list[dict[str, Any]], index: int) -> str:
    if len(items) <= index:
        return 'Not Available'
    return f'{items[index]["raw_value"]:.2f}'


def forecast_points_percent(item: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for point in sequence(item.get('forecast_points')):
        if not isinstance(point, Mapping) or point.get('percent') is None:
            continue
        values.append(max(0.0, min(100.0, float_value(point.get('percent')))))
    return values


def build_utilization_state(payload: Mapping[str, Any]) -> UtilizationState:
    summary = mapping(payload.get('summary'))
    cluster = mapping(payload.get('cluster'))
    cluster_info = mapping(payload.get('cluster_info'))
    risk = mapping(payload.get('risk_assessment'))
    metrics_source_status = mapping(payload.get('metrics_source_status'))
    trends = mapping(payload.get('trends'))
    forecast_payload = mapping(payload.get('forecast_payload'))

    cpu = _resource_metric(summary, risk, 'cpu')
    memory = _resource_metric(summary, risk, 'memory')
    storage = _resource_metric(summary, risk, 'storage')
    pods = _resource_metric(summary, risk, 'pod', display_key='pods')

    total_nodes = int_value(cluster_info.get('total_nodes'))
    ready_nodes = int_value(cluster_info.get('ready_nodes'))
    not_ready_nodes = int_value(cluster_info.get('not_ready_nodes'))

    cpu_consumers = _consumer_rows(sequence(payload.get('top_cpu_consumers')), resource='CPU')
    memory_consumers = _consumer_rows(sequence(payload.get('top_memory_consumers')), resource='Memory')
    _normalize_consumer_bars(cpu_consumers)
    _normalize_consumer_bars(memory_consumers)

    forecast_items = {
        str(item.get('key') or '').lower(): item
        for item in sequence(forecast_payload.get('items'))
        if isinstance(item, Mapping)
    }
    cpu_forecast = mapping(forecast_items.get('cpu'))
    memory_forecast = mapping(forecast_items.get('memory'))
    pod_forecast = mapping(forecast_items.get('pods'))

    return UtilizationState(
        payload=payload,
        summary=summary,
        cluster=cluster,
        metrics_source_status=metrics_source_status,
        forecast_payload=forecast_payload,
        cpu=cpu,
        memory=memory,
        storage=storage,
        pods=pods,
        total_nodes=total_nodes,
        ready_nodes=ready_nodes,
        not_ready_nodes=not_ready_nodes,
        node_participation=_ratio_percent(ready_nodes, total_nodes),
        cpu_consumers=cpu_consumers,
        memory_consumers=memory_consumers,
        forecast_items=forecast_items,
        cpu_forecast=cpu_forecast,
        memory_forecast=memory_forecast,
        pod_forecast=pod_forecast,
        cpu_history=_history_percent(cpu_forecast) or _trend_values(trends.get('cpu')),
        memory_history=_history_percent(memory_forecast) or _trend_values(trends.get('memory')),
        pod_history=_history_percent(pod_forecast) or _trend_values(trends.get('pods')),
        cpu_projection=_forecast_percent(cpu_forecast),
        memory_projection=_forecast_percent(memory_forecast),
        pod_projection=_forecast_percent(pod_forecast),
    )


def _ratio_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(100.0, numerator / denominator * 100.0))


def _resource_metric(
    summary: Mapping[str, Any],
    risk: Mapping[str, Any],
    key: str,
    *,
    display_key: str | None = None,
) -> dict[str, Any]:
    risk_key = display_key or key
    risk_item = mapping(risk.get(risk_key))
    raw = float_value(summary.get(f'{key}_utilization'))
    status = sanitize_text(risk_item.get('status'), fallback=_status_for_percent(raw))
    return {
        'label': (display_key or key).title(),
        'percent': max(0.0, min(100.0, raw)),
        'value': percent(raw),
        'headroom': max(0.0, 100.0 - raw),
        'status': status,
        'tone': _tone_for_status(status, raw),
        'reason': sanitize_text(risk_item.get('reason'), fallback=f'Utilization {percent(raw)}'),
    }


def _status_for_percent(value: float) -> str:
    if value >= 85:
        return 'Critical'
    if value >= 70:
        return 'Review'
    return 'Normal'


def _tone_for_status(status: str, value: float = 0.0) -> str:
    normalized = status.strip().lower()
    if normalized in {'critical', 'failed', 'unavailable'} or value >= 85:
        return 'critical'
    if normalized in {'warning', 'review', 'attention', 'degraded'} or value >= 70:
        return 'warning'
    if normalized in {'normal', 'healthy', 'ready', 'current', 'clear'}:
        return 'normal'
    return 'muted'


def _consumer_rows(items: list[Any], *, resource: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        raw_value = max(0.0, float_value(item.get('value')))
        normalized_value = raw_value if resource == 'CPU' else _memory_value_gib(raw_value)
        result.append(
            {
                'name': sanitize_text(item.get('pod') or item.get('name'), fallback='Unknown Resource'),
                'namespace': sanitize_text(item.get('namespace'), fallback='-'),
                'resource': resource,
                'raw_value': normalized_value,
                'value': f'{normalized_value:.2f} cores' if resource == 'CPU' else f'{normalized_value:.2f} GiB',
                'bar_percent': 0.0,
                'share_percent': 0.0,
            }
        )
    return result


def _memory_value_gib(value: float) -> float:
    if value > 1024**2:
        return value / 1024**3
    return value


def _normalize_consumer_bars(items: list[dict[str, Any]]) -> None:
    max_value = max((item['raw_value'] for item in items), default=0.0)
    total = sum(item['raw_value'] for item in items)
    for item in items:
        item['bar_percent'] = (item['raw_value'] / max_value * 100.0) if max_value else 0.0
        item['share_percent'] = (item['raw_value'] / total * 100.0) if total else 0.0


def _history_percent(item: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for point in sequence(item.get('historical_points')):
        if not isinstance(point, Mapping) or point.get('percent') is None:
            continue
        values.append(max(0.0, min(100.0, float_value(point.get('percent')))))
    return values


def _forecast_percent(item: Mapping[str, Any]) -> float | None:
    value = item.get('projected_percent')
    if value is None:
        return None
    return max(0.0, min(100.0, float_value(value)))


def _trend_values(value: Any) -> list[float]:
    result: list[float] = []
    for point in sequence(value):
        if not isinstance(point, Mapping):
            continue
        raw = point.get('value')
        if raw is not None:
            result.append(max(0.0, min(100.0, float_value(raw))))
    return result
