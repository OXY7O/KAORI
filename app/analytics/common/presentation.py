from __future__ import annotations

from datetime import datetime
from typing import Any


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


def present_capacity_context(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    capacity_summary = result.get('capacity_summary')
    headroom_values: list[float] = []

    if isinstance(capacity_summary, dict):
        for resource in ('cpu', 'memory', 'pods', 'storage'):
            item = capacity_summary.get(resource)
            if not isinstance(item, dict):
                continue
            try:
                headroom = float(item.get('headroom') or 0)
            except (TypeError, ValueError):
                headroom = 0.0
            result[f'{resource}_headroom'] = headroom
            result[f'{resource}_headroom_display'] = percent_display(headroom)
            try:
                capacity = float(item.get('capacity') or 0)
            except (TypeError, ValueError):
                capacity = 0.0
            if capacity > 0:
                headroom_values.append(headroom)

    capacity_headroom_available = bool(headroom_values)
    lowest_headroom = min(headroom_values) if capacity_headroom_available else 0.0
    result['capacity_headroom_available'] = capacity_headroom_available
    result['lowest_headroom'] = lowest_headroom
    result['lowest_headroom_display'] = percent_display(lowest_headroom) if capacity_headroom_available else 'N/A'

    risk_summary = result.get('risk_summary')
    if isinstance(risk_summary, list):
        for item in risk_summary:
            if isinstance(item, dict) and 'headroom' in item:
                item['headroom_display'] = percent_display(item.get('headroom'))
                item['headroom_integer_display'] = percent_display(item.get('headroom'), digits=0)

    for key in ('headroom_nodes', 'capacity_nodes', 'worker_nodes'):
        values = result.get(key)
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and 'headroom' in item:
                    item['headroom_display'] = percent_display(item.get('headroom'))
                    item['headroom_integer_display'] = percent_display(item.get('headroom'), digits=0)
    return result


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
