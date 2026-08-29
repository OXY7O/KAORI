from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.reports.export.html_pdf.normalization import sanitize_text

RESOURCE_UNITS = {
    'cpu': 'cores',
    'memory': 'GiB',
    'pods': 'pods',
    'storage': 'GiB',
}
RESOURCE_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'storage': 'Storage',
}


@dataclass(frozen=True)
class CapacityState:
    cluster: Mapping[str, Any]
    resources: Mapping[str, Mapping[str, Any]]
    allocations: Mapping[str, Mapping[str, Any]]
    total_nodes: int
    ready_nodes: int
    not_ready_nodes: int
    worker_nodes: int
    master_nodes: int
    participation: float
    metrics_source_status: Mapping[str, Any]
    forecast_payload: Mapping[str, Any]


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def number_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def number_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def ratio_percent(numerator: int, denominator: int) -> float:
    return numerator / denominator * 100 if denominator > 0 else 0.0


def percent(value: float) -> str:
    return f'{max(0.0, value):.1f}%'


def optional_percent(value: float | None) -> str:
    return percent(value) if value is not None else 'Not Available'


def metric(label: str, value: str, status: str, tone: str) -> dict[str, str]:
    return {'label': label, 'value': value, 'status': status, 'tone': tone}


def risk_metric(label: str, count: int, tone: str) -> dict[str, str]:
    return metric(
        label,
        str(count),
        'Open' if count else 'Clear',
        tone if count else 'normal',
    )


def capacity_resource(item: Mapping[str, Any], key: str) -> dict[str, Any]:
    evidence_available = bool(item.get('evidence_available')) or number_float(item.get('capacity')) > 0
    capacity = max(0.0, number_float(item.get('capacity')))
    used = max(0.0, number_float(item.get('used')))
    available = max(0.0, number_float(item.get('available')))
    headroom = number_float(item.get('headroom')) if evidence_available else None
    if evidence_available and headroom is not None and headroom <= 0 and capacity > 0:
        headroom = max(0.0, min(100.0, available / capacity * 100))
    used_percent = max(0.0, min(100.0, 100.0 - headroom)) if headroom is not None else 0.0
    status, tone = headroom_status(headroom)
    unit = RESOURCE_UNITS[key]
    return {
        'key': key,
        'label': RESOURCE_LABELS[key],
        'unit': unit,
        'evidence_available': evidence_available,
        'capacity': capacity,
        'used': used,
        'available': available,
        'headroom': headroom,
        'used_percent': used_percent,
        'used_display': percent(used_percent) if evidence_available else 'Not Available',
        'headroom_display': percent(headroom) if headroom is not None else 'Not Available',
        'capacity_display': quantity(capacity, unit) if evidence_available else 'Not Available',
        'available_display': quantity(available, unit) if evidence_available else 'Not Available',
        'used_value_display': quantity(used, unit) if evidence_available else 'Not Available',
        'capacity_value_display': quantity(capacity, unit) if evidence_available else 'Not Available',
        'status': status,
        'tone': tone,
    }


def quantity(value: float, unit: str) -> str:
    if unit == 'pods':
        return f'{int(round(value))} Pods'
    if unit == 'cores':
        return f'{value:.2f} Cores'
    return f'{value:.2f} GiB'


def headroom_status(headroom: float | None) -> tuple[str, str]:
    if headroom is None:
        return 'Not Available', 'muted'
    if headroom < 15:
        return 'Critical', 'critical'
    if headroom < 40:
        return 'Watch', 'warning'
    return 'Healthy', 'normal'


def allocation_resource(section: Mapping[str, Any], key: str) -> dict[str, Any]:
    status = mapping(section.get('status'))
    rows = []
    for item in sequence(section.get('items')):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                'label': sanitize_text(item.get('label'), fallback='Capacity Signal'),
                'display': sanitize_text(item.get('display'), fallback='Not Available'),
                'percent': max(0.0, min(number_float(item.get('percent')), 100.0)),
                'tone': sanitize_text(item.get('tone'), fallback='muted'),
            }
        )
    return {
        'key': key,
        'title': sanitize_text(section.get('title'), fallback=RESOURCE_LABELS[key]),
        'available': bool(section.get('available')),
        'unit': sanitize_text(section.get('unit'), fallback=RESOURCE_UNITS[key]),
        'status': sanitize_text(status.get('label'), fallback='Unknown'),
        'tone': sanitize_text(status.get('tone'), fallback='muted'),
        'items': tuple(rows),
    }


def build_capacity_state(payload: Mapping[str, Any]) -> CapacityState:
    cluster = mapping(payload.get('cluster'))
    cluster_info = mapping(payload.get('cluster_info'))
    capacity_summary = mapping(payload.get('capacity_summary'))
    allocation_summary = mapping(payload.get('allocation_summary'))
    resources = {
        key: capacity_resource(mapping(capacity_summary.get(key)), key)
        for key in ('cpu', 'memory', 'pods', 'storage')
    }
    allocations = {
        key: allocation_resource(mapping(allocation_summary.get(key)), key)
        for key in ('cpu', 'memory', 'pods')
    }
    total_nodes = number_int(cluster_info.get('total_nodes'))
    ready_nodes = number_int(cluster_info.get('ready_nodes'))
    return CapacityState(
        cluster=cluster,
        resources=resources,
        allocations=allocations,
        total_nodes=total_nodes,
        ready_nodes=ready_nodes,
        not_ready_nodes=number_int(cluster_info.get('not_ready_nodes')),
        worker_nodes=number_int(cluster_info.get('worker_nodes')),
        master_nodes=number_int(cluster_info.get('master_nodes')),
        participation=ratio_percent(ready_nodes, total_nodes),
        metrics_source_status=mapping(payload.get('metrics_source_status')),
        forecast_payload=mapping(payload.get('forecast_payload')),
    )
