from __future__ import annotations

from typing import Any, Callable

from app.analytics.capacity.evidence import AllocationEvidence, CapacityEvidence, ScalarEvidence
from app.analytics.common.base_service import bytes_to_gib, clamp_percent, raw_percent, safe_percent, safe_round

SCHEDULING_RESOURCES = ('cpu', 'memory', 'pods')
RESOURCE_DISPLAY_LABELS = {
    'cpu': 'CPU',
    'memory': 'Memory',
    'pods': 'Pods',
    'storage': 'Node Filesystem',
}


def resource_display_label(resource: str) -> str:
    return RESOURCE_DISPLAY_LABELS.get(resource, resource.replace('_', ' ').title())


def allocation_pressure_tone(percent: float) -> str:
    if percent >= 100:
        return 'critical'
    if percent >= 75:
        return 'warning'
    return 'normal'


def allocation_headroom_tone(percent: float) -> str:
    if percent < 15:
        return 'critical'
    if percent < 40:
        return 'warning'
    return 'normal'


def build_capacity_summary(evidence: CapacityEvidence) -> dict[str, dict[str, Any]]:
    return {
        'cpu': _schedulable_resource(
            evidence.cpu.allocatable,
            evidence.cpu.actual,
            converter=lambda value: safe_round(value),
            scope_label='Ready worker allocatable CPU',
        ),
        'memory': _schedulable_resource(
            evidence.memory.allocatable,
            evidence.memory.actual,
            converter=bytes_to_gib,
            scope_label='Ready worker allocatable memory',
        ),
        'pods': _schedulable_resource(
            evidence.pod_capacity,
            evidence.current_pods,
            converter=lambda value: safe_round(value, 0),
            scope_label='Ready worker allocatable pod slots',
        ),
        'storage': _filesystem_reference(evidence),
    }


def _schedulable_resource(
    capacity: ScalarEvidence,
    usage: ScalarEvidence,
    *,
    converter: Callable[[float], float],
    scope_label: str,
) -> dict[str, Any]:
    capacity_available = capacity.positive
    usage_available = usage.available
    complete = capacity_available and usage_available
    remaining = max(capacity.value - usage.value, 0) if complete else None
    return {
        'evidence_available': complete,
        'capacity_evidence_available': capacity_available,
        'usage_evidence_available': usage_available,
        'capacity': converter(capacity.value) if capacity_available else None,
        'used': converter(usage.value) if usage_available else None,
        'available': converter(remaining) if remaining is not None else None,
        'headroom': safe_percent(remaining, capacity.value) if remaining is not None else None,
        'scheduling_resource': True,
        'scope_label': scope_label,
    }


def _filesystem_reference(evidence: CapacityEvidence) -> dict[str, Any]:
    capacity = evidence.filesystem_capacity
    used = evidence.filesystem_used
    available = evidence.filesystem_available
    capacity_available = capacity.positive
    complete = capacity_available and used.available and available.available
    return {
        'evidence_available': complete,
        'capacity_evidence_available': capacity_available,
        'usage_evidence_available': used.available,
        'capacity': bytes_to_gib(capacity.value) if capacity_available else None,
        'used': bytes_to_gib(used.value) if used.available else None,
        'available': bytes_to_gib(available.value) if available.available else None,
        'headroom': safe_percent(available.value, capacity.value) if complete else None,
        'scheduling_resource': False,
        'scope_label': 'Operational node-filesystem reference; not Kubernetes allocatable capacity',
    }


def build_allocation_summary(evidence: CapacityEvidence) -> dict[str, dict[str, Any]]:
    return {
        'cpu': _allocation_section('cpu', evidence.cpu, value_converter=lambda value: safe_round(value)),
        'memory': _allocation_section('memory', evidence.memory, value_converter=bytes_to_gib),
        'pods': _pod_allocation_section(evidence.pod_capacity, evidence.current_pods),
    }


def _allocation_section(
    resource: str,
    evidence: AllocationEvidence,
    *,
    value_converter: Callable[[float], float],
) -> dict[str, Any]:
    allocatable = evidence.allocatable
    status = allocation_status(resource, evidence)
    items = [
        _allocation_item('Allocatable', allocatable, allocatable, resource, value_converter, fixed_tone='normal'),
        _allocation_item('Configured Requests', evidence.requests, allocatable, resource, value_converter),
        _allocation_item('Configured Limits', evidence.limits, allocatable, resource, value_converter),
        _allocation_item('Actual Avg Usage', evidence.actual, allocatable, resource, value_converter),
        _allocation_item('Peak Usage', evidence.peak, allocatable, resource, value_converter),
    ]
    return {
        'title': resource_display_label(resource),
        'available': allocatable.positive,
        'complete': all(item['available'] for item in items),
        'unit': 'cores' if resource == 'cpu' else 'GiB',
        'status': status,
        'items': items,
        'missing_metrics': status.get('missing_metrics', []),
    }


def _pod_allocation_section(capacity: ScalarEvidence, current: ScalarEvidence) -> dict[str, Any]:
    capacity_available = capacity.positive
    remaining = ScalarEvidence(
        value=max(capacity.value - current.value, 0),
        available=capacity_available and current.available,
    )
    items = [
        _allocation_item('Pod Capacity', capacity, capacity, 'pods', lambda value: safe_round(value, 0), fixed_tone='normal'),
        _allocation_item('Current Pods', current, capacity, 'pods', lambda value: safe_round(value, 0)),
        _allocation_item(
            'Remaining Pod Slots',
            remaining,
            capacity,
            'pods',
            lambda value: safe_round(value, 0),
            headroom=True,
        ),
    ]
    status = pod_allocation_status(capacity, current)
    return {
        'title': 'Pods',
        'available': capacity_available,
        'complete': all(item['available'] for item in items),
        'unit': 'pods',
        'status': status,
        'items': items,
        'missing_metrics': status.get('missing_metrics', []),
    }


def _allocation_item(
    label: str,
    evidence: ScalarEvidence,
    allocatable: ScalarEvidence,
    resource: str,
    converter: Callable[[float], float],
    *,
    fixed_tone: str | None = None,
    headroom: bool = False,
) -> dict[str, Any]:
    available = evidence.available and allocatable.positive
    raw_value = raw_percent(evidence.value, allocatable.value) if available else None
    percent = clamp_percent(raw_value or 0) if available else None
    tone = fixed_tone or (
        allocation_headroom_tone(raw_value or 0)
        if headroom
        else allocation_pressure_tone(raw_value or 0)
    )
    return {
        'label': label,
        'available': available,
        'value': converter(evidence.value) if evidence.available else None,
        'display': _allocation_display(resource, converter(evidence.value), raw_value) if available else 'N/A',
        'raw_percent': safe_round(raw_value, 1) if raw_value is not None else None,
        'percent': percent,
        'tone': tone if available else 'unknown',
    }


def _allocation_display(resource: str, value: float, percent: float | None) -> str:
    if resource == 'cpu':
        value_display = f'{value:.2f} cores'
    elif resource == 'memory':
        value_display = f'{value:.2f} GiB'
    else:
        value_display = f'{value:.0f} pods'
    return f'{value_display} ({safe_round(percent or 0, 1):.1f}%)'


def allocation_status(resource: str, evidence: AllocationEvidence) -> dict[str, Any]:
    if not evidence.allocatable.positive:
        return _status('Unknown', 'unknown', 'Allocatable capacity evidence is unavailable.')

    percentages = {
        'requests': _evidence_percent(evidence.requests, evidence.allocatable),
        'limits': _evidence_percent(evidence.limits, evidence.allocatable),
        'actual': _evidence_percent(evidence.actual, evidence.allocatable),
        'peak': _evidence_percent(evidence.peak, evidence.allocatable),
    }
    missing = [label for label, value in percentages.items() if value is None]

    if percentages['requests'] is not None and percentages['requests'] >= 100:
        return _status(
            f'{resource_display_label(resource)} Request Overcommit',
            'critical',
            'Configured requests meet or exceed Ready-worker allocatable capacity.',
            missing,
        )
    if percentages['peak'] is not None and percentages['peak'] >= 100:
        return _status(
            f'{resource_display_label(resource)} Peak Over Capacity',
            'critical',
            'Observed peak usage met or exceeded Ready-worker allocatable capacity.',
            missing,
        )
    if percentages['actual'] is not None and percentages['actual'] >= 95:
        return _status(
            f'{resource_display_label(resource)} Usage Critical',
            'critical',
            'Current usage is at least 95% of Ready-worker allocatable capacity.',
            missing,
        )
    if percentages['limits'] is not None and percentages['limits'] >= 100:
        return _status(
            f'{resource_display_label(resource)} Limit Overcommit',
            'warning',
            'Configured limits exceed the Ready-worker allocatable envelope.',
            missing,
        )

    known = [value for value in percentages.values() if value is not None]
    pressure = max(known, default=0)
    if pressure >= 90:
        return _status('Near Capacity', 'warning', 'At least one known commitment or usage signal is at 90% or higher.', missing)
    if pressure >= 75:
        return _status('Watch', 'warning', 'At least one known commitment or usage signal is at 75% or higher.', missing)
    if missing:
        return _status('Limited Evidence', 'unknown', 'Some commitment or usage signals are unavailable.', missing)
    return _status('Healthy', 'normal', 'Requests, limits, current usage, and peak usage remain within the current envelope.')


def pod_allocation_status(capacity: ScalarEvidence, current: ScalarEvidence) -> dict[str, Any]:
    if not capacity.positive:
        return _status('Unknown', 'unknown', 'Pod allocatable capacity evidence is unavailable.')
    if not current.available:
        return _status('Limited Evidence', 'unknown', 'Current pod placement evidence is unavailable.', ['current pods'])
    percent = raw_percent(current.value, capacity.value)
    if percent >= 95:
        return _status('Pod Capacity Critical', 'critical', 'Current pods consume at least 95% of Ready-worker pod slots.')
    if percent >= 75:
        return _status('Watch', 'warning', 'Current pods consume at least 75% of Ready-worker pod slots.')
    return _status('Healthy', 'normal', 'Current pod placement remains within the Ready-worker pod envelope.')


def _evidence_percent(value: ScalarEvidence, allocatable: ScalarEvidence) -> float | None:
    if not value.available or not allocatable.positive:
        return None
    return raw_percent(value.value, allocatable.value)


def _status(
    label: str,
    tone: str,
    reason: str,
    missing_metrics: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'label': label,
        'tone': tone,
        'reason': reason,
        'missing_metrics': missing_metrics or [],
    }


def build_capacity_posture(
    capacity_summary: dict[str, dict[str, Any]],
    allocation_summary: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    statuses = [
        allocation_summary.get(resource, {}).get('status', {})
        for resource in SCHEDULING_RESOURCES
    ]
    evidence_complete = all(
        bool(capacity_summary.get(resource, {}).get('evidence_available'))
        and bool(allocation_summary.get(resource, {}).get('complete'))
        for resource in SCHEDULING_RESOURCES
    )

    critical = next(
        (
            status
            for status in statuses
            if isinstance(status, dict) and status.get('tone') == 'critical'
        ),
        None,
    )
    if critical is not None:
        return {
            'label': 'Critical',
            'tone': 'critical',
            'reason': str(
                critical.get('reason')
                or 'A scheduling capacity signal is critical.'
            ),
            'evidence_complete': evidence_complete,
        }

    warning = next(
        (
            status
            for status in statuses
            if isinstance(status, dict) and status.get('tone') == 'warning'
        ),
        None,
    )
    if warning is not None:
        return {
            'label': 'Watch',
            'tone': 'warning',
            'reason': str(
                warning.get('reason')
                or 'A scheduling capacity signal requires attention.'
            ),
            'evidence_complete': evidence_complete,
        }

    if evidence_complete:
        return {
            'label': 'Healthy',
            'tone': 'normal',
            'reason': (
                'Ready-worker allocatable, commitment, current usage, and peak evidence '
                'are complete and remain within the configured envelope.'
            ),
            'evidence_complete': True,
        }

    has_evidence = any(
        bool(capacity_summary.get(resource, {}).get('capacity_evidence_available'))
        or bool(capacity_summary.get(resource, {}).get('usage_evidence_available'))
        or (
            isinstance(status, dict)
            and str(status.get('label') or 'Unknown') not in {'', 'Unknown'}
        )
        for resource, status in zip(SCHEDULING_RESOURCES, statuses)
    )
    if has_evidence:
        return {
            'label': 'Limited Evidence',
            'tone': 'unknown',
            'reason': (
                'Some Ready-worker allocation, usage, or peak signals are unavailable; '
                'the scheduling envelope cannot be declared Healthy.'
            ),
            'evidence_complete': False,
        }
    return {
        'label': 'Unknown',
        'tone': 'unknown',
        'reason': 'Ready-worker scheduling evidence is unavailable.',
        'evidence_complete': False,
    }


def build_cluster_info(
    evidence: CapacityEvidence,
    *,
    kubernetes_version: str,
    total_nodes: int,
    ready_nodes: int,
    not_ready_nodes: int,
    control_plane_nodes: int,
) -> dict[str, Any]:
    worker_available = evidence.worker_nodes.available
    ready_available = evidence.ready_worker_nodes.available
    worker_nodes = int(round(evidence.worker_nodes.value)) if worker_available else None
    ready_workers = int(round(evidence.ready_worker_nodes.value)) if ready_available else None
    not_ready_workers = (
        max(worker_nodes - ready_workers, 0)
        if worker_nodes is not None and ready_workers is not None
        else None
    )
    return {
        'kubernetes_version': kubernetes_version,
        'total_nodes': total_nodes,
        'worker_nodes': worker_nodes,
        'ready_worker_nodes': ready_workers,
        'not_ready_worker_nodes': not_ready_workers,
        'worker_node_evidence_available': worker_available and ready_available,
        'master_nodes': control_plane_nodes,
        # Existing report publications retain the full-cluster readiness context.
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
    }


def build_kpi_cards(
    cluster_info: dict[str, Any],
    capacity_summary: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    worker_available = bool(cluster_info.get('worker_node_evidence_available'))
    worker_nodes = cluster_info.get('worker_nodes')
    ready_workers = cluster_info.get('ready_worker_nodes')
    not_ready_workers = cluster_info.get('not_ready_worker_nodes')
    return [
        {
            'label': 'Worker Nodes',
            'value': worker_nodes if worker_available else 'N/A',
            'caption': (
                f'{ready_workers} Ready, {not_ready_workers} Not Ready'
                if worker_available
                else 'Worker readiness evidence unavailable'
            ),
            'footer': (
                f'Total nodes {cluster_info.get("total_nodes", 0)} · '
                f'Control-plane {cluster_info.get("master_nodes", 0)}'
            ),
            'icon': 'users',
            'available': worker_available,
        },
        _capacity_kpi('Allocatable CPU', capacity_summary['cpu'], 'Cores', 'cpu'),
        _capacity_kpi('Allocatable Memory', capacity_summary['memory'], 'GiB', 'memory-stick'),
        _capacity_kpi('Pod Capacity', capacity_summary['pods'], 'Pods', 'box', digits=0),
    ]


def _capacity_kpi(
    label: str,
    item: dict[str, Any],
    unit: str,
    icon: str,
    *,
    digits: int = 2,
) -> dict[str, Any]:
    available = bool(item.get('capacity_evidence_available'))
    value = item.get('capacity')
    value_display = f'{float(value):.{digits}f} {unit}' if available and value is not None else 'N/A'
    return {
        'label': label,
        'value': value_display,
        'caption': 'Ready worker nodes only',
        'footer': '',
        'icon': icon,
        'available': available,
    }


def build_risk_summary(capacity_summary: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    icon_map = {'cpu': 'cpu', 'memory': 'memory-stick', 'pods': 'boxes', 'storage': 'hard-drive'}
    risks: list[dict[str, Any]] = []
    for resource in ('cpu', 'memory', 'pods', 'storage'):
        item = capacity_summary.get(resource, {})
        available = bool(item.get('evidence_available')) and item.get('headroom') is not None
        headroom = float(item['headroom']) if available else None
        status = headroom_status(headroom) if available else {'label': 'Unknown', 'tone': 'unknown'}
        risks.append(
            {
                'resource': resource,
                'label': resource_display_label(resource),
                'headroom': headroom,
                'evidence_available': available,
                'scheduling_resource': bool(item.get('scheduling_resource', resource != 'storage')),
                'scope_label': item.get('scope_label', ''),
                'status': status,
                'icon': icon_map.get(resource, 'activity'),
            }
        )
    return risks


def headroom_status(headroom: float) -> dict[str, str]:
    if headroom < 15:
        return {'label': 'Critical', 'tone': 'critical'}
    if headroom < 40:
        return {'label': 'Watch', 'tone': 'warning'}
    return {'label': 'Healthy', 'tone': 'normal'}


def build_governance_findings(
    capacity_summary: dict[str, dict[str, Any]],
    allocation_summary: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for resource in ('cpu', 'memory', 'pods'):
        section = allocation_summary.get(resource, {})
        status = section.get('status', {}) if isinstance(section, dict) else {}
        tone = str(status.get('tone', 'unknown'))
        if tone in {'critical', 'warning'}:
            findings.append(
                {
                    'label': f'{resource_display_label(resource)} allocation status: {status.get("label", "Unknown")}',
                    'severity': tone,
                    'tone': tone,
                    'icon': {'cpu': 'cpu', 'memory': 'memory-stick', 'pods': 'box'}[resource],
                    'filter': 'capacity-allocation',
                }
            )
        elif status.get('label') == 'Limited Evidence':
            findings.append(
                {
                    'label': f'{resource_display_label(resource)} commitment evidence is incomplete',
                    'severity': 'info',
                    'tone': 'info',
                    'icon': 'database-zap',
                    'filter': 'capacity-evidence',
                }
            )

    low_headroom = [
        resource_display_label(resource)
        for resource in SCHEDULING_RESOURCES
        if capacity_summary.get(resource, {}).get('evidence_available')
        and float(capacity_summary[resource].get('headroom') or 0) < 30
    ]
    if low_headroom:
        findings.append(
            {
                'label': f'Low Ready-worker headroom detected on {", ".join(low_headroom)}',
                'severity': 'critical',
                'tone': 'critical',
                'icon': 'circle-alert',
                'filter': 'capacity-headroom',
            }
        )

    if not findings:
        findings.append(
            {
                'label': 'No actionable capacity governance finding detected',
                'severity': 'normal',
                'tone': 'normal',
                'icon': 'check-circle',
                'filter': '',
            }
        )
    return findings
