from __future__ import annotations

from typing import Any

from app.analytics.common.presentation import percent_display

_RESOURCE_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'storage': 'Node Filesystem',
}
_SCHEDULING_RESOURCES = ('cpu', 'memory', 'pods')
_ALL_RESOURCES = (*_SCHEDULING_RESOURCES, 'storage')


def _capacity_status(headroom: float | None, available: bool) -> tuple[str, str]:
    if not available or headroom is None:
        return 'Unknown', 'unknown'
    if headroom < 15:
        return 'Critical', 'critical'
    if headroom < 40:
        return 'Watch', 'warning'
    return 'Healthy', 'normal'


def present_capacity_context(context: dict[str, Any]) -> dict[str, Any]:
    result = dict(context)
    raw_summary = result.get('capacity_summary')
    capacity_summary = raw_summary if isinstance(raw_summary, dict) else {}
    normalized, scheduling_headroom = _normalize_capacity_summary(capacity_summary)

    result['capacity_summary'] = normalized
    result['capacity_headroom_available'] = bool(scheduling_headroom)
    for resource, item in normalized.items():
        headroom = item.get('headroom')
        available = bool(item.get('evidence_available'))
        result[f'{resource}_headroom'] = headroom
        result[f'{resource}_headroom_display'] = (
            percent_display(headroom) if available else 'N/A'
        )

    complete_scheduling_evidence = _complete_scheduling_evidence(
        normalized,
        result.get('allocation_summary'),
    )
    posture = _resolve_posture(
        result.get('capacity_posture'),
        scheduling_headroom,
        complete_scheduling_evidence,
    )
    complete_scheduling_evidence = bool(
        posture.get('evidence_complete', complete_scheduling_evidence)
    )
    result['capacity_posture'] = posture
    result['capacity_scheduling_evidence_complete'] = complete_scheduling_evidence
    result['capacity_scheduling_evidence_partial'] = (
        bool(scheduling_headroom) and not complete_scheduling_evidence
    )
    result.update(_bottleneck_presentation(scheduling_headroom))
    _present_risk_summary(result.get('risk_summary'))
    return result


def _normalize_capacity_summary(
    capacity_summary: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, float]]]:
    normalized: dict[str, dict[str, Any]] = {}
    scheduling_headroom: list[tuple[str, float]] = []
    for resource in _ALL_RESOURCES:
        raw_item = capacity_summary.get(resource)
        item = _normalize_resource(
            resource,
            dict(raw_item) if isinstance(raw_item, dict) else {},
        )
        normalized[resource] = item
        if item['scheduling_resource'] and item['headroom'] is not None:
            scheduling_headroom.append((resource, float(item['headroom'])))
    return normalized, scheduling_headroom


def _normalize_resource(resource: str, item: dict[str, Any]) -> dict[str, Any]:
    capacity = _optional_float(item.get('capacity'))
    used = _optional_float(item.get('used'))
    remaining = _optional_float(item.get('available'))
    headroom = _optional_float(item.get('headroom'))

    capacity_available = bool(
        item.get('capacity_evidence_available', capacity is not None and capacity > 0)
    ) and capacity is not None and capacity > 0
    usage_available = bool(
        item.get('usage_evidence_available', used is not None)
    ) and used is not None
    evidence_available = bool(
        item.get(
            'evidence_available',
            capacity_available
            and usage_available
            and remaining is not None
            and headroom is not None,
        )
    )
    scheduling_resource = bool(item.get('scheduling_resource', resource != 'storage'))

    normalized_headroom = (
        round(max(min(headroom, 100.0), 0.0), 1)
        if evidence_available and headroom is not None
        else None
    )
    utilization = (
        round(max(min(100.0 - normalized_headroom, 100.0), 0.0), 1)
        if normalized_headroom is not None
        else None
    )
    status_label, tone = _capacity_status(normalized_headroom, evidence_available)

    item.update(
        {
            'capacity_evidence_available': capacity_available,
            'usage_evidence_available': usage_available,
            'evidence_available': evidence_available,
            'scheduling_resource': scheduling_resource,
            'scope_label': str(
                item.get('scope_label')
                or _default_scope_label(resource)
            ),
            'capacity': (
                round(capacity, 2)
                if capacity_available and capacity is not None
                else None
            ),
            'used': round(used, 2) if usage_available and used is not None else None,
            'available': (
                round(remaining, 2)
                if evidence_available and remaining is not None
                else None
            ),
            'headroom': normalized_headroom,
            'utilization_percent': utilization,
            'status_label': status_label,
            'tone': tone,
        }
    )
    return item


def _default_scope_label(resource: str) -> str:
    if resource == 'storage':
        return 'Operational node-filesystem reference; not Kubernetes allocatable capacity'
    return 'Ready worker allocatable capacity'


def _complete_scheduling_evidence(
    normalized: dict[str, dict[str, Any]],
    raw_allocation_summary: Any,
) -> bool:
    allocation_summary = (
        raw_allocation_summary if isinstance(raw_allocation_summary, dict) else {}
    )
    return all(
        bool(normalized[resource].get('evidence_available'))
        and bool(
            allocation_summary.get(resource, {}).get('complete')
            if isinstance(allocation_summary.get(resource), dict)
            else False
        )
        for resource in _SCHEDULING_RESOURCES
    )


def _resolve_posture(
    raw_posture: Any,
    scheduling_headroom: list[tuple[str, float]],
    complete_scheduling_evidence: bool,
) -> dict[str, Any]:
    posture = dict(raw_posture) if isinstance(raw_posture, dict) else {}
    if posture.get('label'):
        return posture
    if complete_scheduling_evidence and scheduling_headroom:
        lowest_known = min(scheduling_headroom, key=lambda candidate: candidate[1])[1]
        label, tone = _capacity_status(lowest_known, True)
        return {
            'label': label,
            'tone': tone,
            'reason': 'All Ready-worker scheduling evidence is complete.',
            'evidence_complete': True,
        }
    if scheduling_headroom:
        return {
            'label': 'Limited Evidence',
            'tone': 'unknown',
            'reason': 'Some Ready-worker scheduling evidence is unavailable.',
            'evidence_complete': False,
        }
    return {
        'label': 'Unknown',
        'tone': 'unknown',
        'reason': 'Ready-worker scheduling evidence is unavailable.',
        'evidence_complete': False,
    }


def _bottleneck_presentation(
    scheduling_headroom: list[tuple[str, float]],
) -> dict[str, Any]:
    if not scheduling_headroom:
        return {
            'lowest_headroom': None,
            'lowest_headroom_display': 'N/A',
            'lowest_headroom_resource': None,
            'lowest_headroom_resource_label': 'Unavailable',
            'lowest_headroom_metric_display': 'N/A',
        }
    resource, headroom = min(scheduling_headroom, key=lambda candidate: candidate[1])
    label = _RESOURCE_LABELS[resource]
    return {
        'lowest_headroom': headroom,
        'lowest_headroom_display': percent_display(headroom),
        'lowest_headroom_resource': resource,
        'lowest_headroom_resource_label': label,
        'lowest_headroom_metric_display': f'{label} · {percent_display(headroom)}',
    }


def _present_risk_summary(raw_risk_summary: Any) -> None:
    if not isinstance(raw_risk_summary, list):
        return
    for item in raw_risk_summary:
        if not isinstance(item, dict):
            continue
        available = bool(item.get('evidence_available', False))
        headroom = item.get('headroom') if available else None
        item['headroom_display'] = percent_display(headroom) if available else 'N/A'
        item['headroom_integer_display'] = (
            percent_display(headroom, digits=0) if available else 'N/A'
        )


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
