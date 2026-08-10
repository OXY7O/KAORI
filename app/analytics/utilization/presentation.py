from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.analytics.common.coercion import safe_float, safe_int

_RESOURCE_SPECS = (
    {
        'key': 'cpu',
        'label': 'CPU',
        'icon': 'cpu',
        'value_key': 'cpu_utilization',
        'usage_key': 'cpu_usage',
        'capacity_key': 'cpu_capacity',
        'description': 'Processor usage against worker allocatable CPU.',
        'unit': 'cores',
    },
    {
        'key': 'memory',
        'label': 'Memory',
        'icon': 'memory-stick',
        'value_key': 'memory_utilization',
        'usage_key': 'memory_usage',
        'capacity_key': 'memory_capacity',
        'description': 'Working-set memory against worker allocatable memory.',
        'unit': 'bytes',
    },
    {
        'key': 'storage',
        'label': 'Node Filesystem',
        'short_label': 'Storage',
        'icon': 'hard-drive',
        'value_key': 'storage_utilization',
        'usage_key': 'storage_usage',
        'capacity_key': 'storage_capacity',
        'description': 'Mounted /var or / filesystem usage across canonical nodes.',
        'unit': 'bytes',
    },
    {
        'key': 'pods',
        'label': 'Pod Density',
        'short_label': 'Pods',
        'icon': 'boxes',
        'value_key': 'pod_utilization',
        'usage_key': 'pod_count',
        'capacity_key': 'pod_capacity',
        'description': 'Running pods against worker allocatable pod capacity.',
        'unit': 'pods',
    },
)

_TREND_LABELS = {
    1: 'Last 1 Hour',
    6: 'Last 6 Hours',
    12: 'Last 12 Hours',
    24: 'Last 24 Hours',
    168: 'Last 7 Days',
    720: 'Last 30 Days',
    1440: 'Last 60 Days',
}


def utilization_tone(value: float | None) -> str:
    if value is None:
        return 'unknown'
    if value > 90:
        return 'critical'
    if value >= 75:
        return 'warning'
    return 'normal'


def utilization_status(value: float | None) -> str:
    return {
        'critical': 'Critical',
        'warning': 'Warning',
        'normal': 'Normal',
        'unknown': 'Unknown',
    }[utilization_tone(value)]


def trend_range_label(hours: int) -> str:
    return _TREND_LABELS.get(hours, f'Last {hours} Hours')


def build_trend_options(allowed_hours: tuple[int, ...] | list[int], selected_hours: int) -> list[dict[str, Any]]:
    return [
        {
            'value': hours,
            'label': trend_range_label(hours),
            'selected': hours == selected_hours,
        }
        for hours in allowed_hours
    ]


def _format_resource_detail(spec: Mapping[str, Any], usage: float, capacity: float) -> str:
    unit = spec['unit']
    if unit == 'bytes':
        return f'{usage / 1024**3:.2f} GiB / {capacity / 1024**3:.2f} GiB'
    if unit == 'pods':
        return f'{int(round(usage))} / {int(round(capacity))} Pods'
    return f'{usage:.2f} / {capacity:.2f} Cores'


def build_resource_rows(summary: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    source = summary if isinstance(summary, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for spec in _RESOURCE_SPECS:
        usage = safe_float(source.get(spec['usage_key']))
        capacity = safe_float(source.get(spec['capacity_key']))
        available = spec['capacity_key'] in source and capacity > 0
        value = round(safe_float(source.get(spec['value_key'])), 2) if available else None
        rows.append(
            {
                **spec,
                'short_label': spec.get('short_label', spec['label']),
                'usage': usage,
                'capacity': capacity,
                'available': available,
                'value': value,
                'value_display': f'{value:.1f}%' if value is not None else 'N/A',
                'detail': (
                    _format_resource_detail(spec, usage, capacity) if available else 'Capacity evidence unavailable'
                ),
                'tone': utilization_tone(value),
                'status': utilization_status(value),
                'progress_value': max(0.0, min(100.0, value or 0.0)),
            }
        )
    return rows


def build_summary_presentation(
    *,
    summary: Mapping[str, Any] | None,
    cluster_info: Mapping[str, Any] | None,
    trend_hours: int,
) -> dict[str, Any]:
    rows = build_resource_rows(summary)
    available_rows = [row for row in rows if row['available']]
    highest = max(available_rows, key=lambda row: row['value'] or 0.0, default=None)
    has_critical = any(row['tone'] == 'critical' for row in available_rows)
    has_warning = any(row['tone'] == 'warning' for row in available_rows)

    if has_critical:
        posture_label, posture_tone = 'Critical', 'critical'
    elif has_warning:
        posture_label, posture_tone = 'Watch', 'warning'
    elif len(available_rows) == len(rows):
        posture_label, posture_tone = 'Healthy', 'normal'
    elif available_rows:
        posture_label, posture_tone = 'Limited Evidence', 'warning'
    else:
        posture_label, posture_tone = 'Unknown', 'unknown'

    cluster = cluster_info if isinstance(cluster_info, Mapping) else {}
    total_nodes = safe_int(cluster.get('total_nodes'))
    ready_nodes = safe_int(cluster.get('ready_nodes'))
    ready_ratio = round((ready_nodes / total_nodes) * 100) if total_nodes > 0 else None

    return {
        'resource_rows': rows,
        'evidence_available': bool(available_rows),
        'evidence_complete': len(available_rows) == len(rows),
        'highest_label': highest['short_label'] if highest else 'No evidence',
        'highest_value': highest['value'] if highest else None,
        'highest_value_display': highest['value_display'] if highest else 'N/A',
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'ready_ratio': ready_ratio,
        'ready_ratio_display': f'{ready_ratio}%' if ready_ratio is not None else 'N/A',
        'time_range_label': trend_range_label(trend_hours),
    }


def build_trend_presentation(
    *,
    trend_summary: Mapping[str, Any] | None,
    trend_hours: int,
    selected_node: str,
) -> dict[str, Any]:
    source = trend_summary if isinstance(trend_summary, Mapping) else {}
    raw_resources = source.get('resources')
    resources = raw_resources if isinstance(raw_resources, Mapping) else {}
    rows: list[dict[str, Any]] = []
    for key, label, icon in (
        ('cpu', 'CPU', 'cpu'),
        ('memory', 'Memory', 'memory-stick'),
        ('pods', 'Pods', 'boxes'),
    ):
        raw_metric = resources.get(key)
        metric = raw_metric if isinstance(raw_metric, Mapping) else {}
        sample_count = safe_int(metric.get('sample_count'))
        available = sample_count > 0
        current = round(safe_float(metric.get('current')), 2) if available else None
        average = round(safe_float(metric.get('average')), 2) if available else None
        peak = round(safe_float(metric.get('peak')), 2) if available else None
        rows.append(
            {
                'key': key,
                'label': label,
                'icon': icon,
                'available': available,
                'current': current,
                'current_display': f'{current:.2f}%' if current is not None else 'N/A',
                'average': average,
                'average_display': f'{average:.2f}%' if average is not None else 'N/A',
                'peak': peak,
                'peak_display': f'{peak:.2f}%' if peak is not None else 'N/A',
                'tone': utilization_tone(current),
                'progress_value': max(0.0, min(100.0, current or 0.0)),
            }
        )

    available_rows = [row for row in rows if row['available']]
    current_highest = max(available_rows, key=lambda row: row['current'] or 0.0, default=None)
    peak_row = max(available_rows, key=lambda row: row['peak'] or 0.0, default=None)
    peak_value = peak_row['peak'] if peak_row else None
    return {
        'resource_rows': rows,
        'current_highest_label': current_highest['label'] if current_highest else 'No evidence',
        'current_highest_display': current_highest['current_display'] if current_highest else 'N/A',
        'peak_value_display': f'{peak_value:.2f}%' if peak_value is not None else 'N/A',
        'peak_resource': peak_row['label'] if peak_row else 'None',
        'sample_count': safe_int(source.get('sample_count')),
        'posture': str(source.get('posture') or 'No Data'),
        'tone': str(source.get('tone') or 'unknown'),
        'selected_scope': selected_node or 'All Worker Nodes',
        'time_range_label': trend_range_label(trend_hours),
    }


def build_node_presentation(
    *,
    detail_summary: Mapping[str, Any] | None,
    risk_assessment: Mapping[str, Any] | None,
    selected_node: str,
) -> dict[str, Any]:
    summary = detail_summary if isinstance(detail_summary, Mapping) else {}
    risks = risk_assessment if isinstance(risk_assessment, Mapping) else {}
    all_rows = build_resource_rows(summary)
    resource_rows = []
    for row in all_rows:
        if row['key'] == 'storage':
            continue
        raw_risk = risks.get(row['key'])
        risk = raw_risk if isinstance(raw_risk, Mapping) else {}
        row = dict(row)
        row['reason'] = str(risk.get('reason') or ('Evidence unavailable' if not row['available'] else '-'))
        row['tone'] = utilization_tone(row['value']) if row['available'] else 'unknown'
        resource_rows.append(row)

    storage = next(row for row in all_rows if row['key'] == 'storage')
    raw_storage_risk = risks.get('storage')
    storage_risk = raw_storage_risk if isinstance(raw_storage_risk, Mapping) else {}
    storage['reason'] = str(
        storage_risk.get('reason')
        or (
            'Restore filesystem capacity evidence before taking action.'
            if not storage['available']
            else 'Review Filesystem Pressure'
        )
    )
    storage['usage_summary'] = (
        f'{storage["usage"] / 1024**3:.2f} GiB used from {storage["capacity"] / 1024**3:.2f} GiB capacity.'
        if storage['available']
        else 'Filesystem capacity and usage evidence is unavailable for this scope.'
    )

    return {
        'selected_scope': selected_node or 'All Nodes',
        'filesystem_scope': str(summary.get('storage_scope') or 'Canonical node filesystems'),
        'resource_rows': resource_rows,
        'storage': storage,
    }
