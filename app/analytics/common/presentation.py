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
        return f'{float(value_bytes or 0) / (1024 ** 3):.{digits}f} GiB'
    except (TypeError, ValueError):
        return '0.00 GiB'


def datetime_display(value: datetime | None, *, fallback: str = 'Not recorded') -> str:
    if value is None:
        return fallback
    return value.strftime('%d %b %Y, %H:%M %Z').strip()


def present_capacity_context(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    result['cpu_headroom_display'] = percent_display(result.get('cpu_headroom'))
    result['memory_headroom_display'] = percent_display(result.get('memory_headroom'))
    result['pod_headroom_display'] = percent_display(result.get('pod_headroom'))
    result['lowest_headroom_display'] = percent_display(result.get('lowest_headroom'))
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
