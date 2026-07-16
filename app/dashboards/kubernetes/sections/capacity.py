from __future__ import annotations

from typing import Any

from app.dashboards.kubernetes.schema import CapacityItem, CapacitySnapshot
from app.dashboards.kubernetes.utils import (
    capacity_insight,
    risk_from_percent,
    safe_float,
    safe_optional_float,
)


def build_capacity_snapshot(*, live_cluster: Any | None, selected_cluster_id: str | None) -> CapacitySnapshot:
    if live_cluster is None:
        return empty_capacity_snapshot(
            insight='Select a specific cluster to show worker-node capacity and headroom from Prometheus.'
            if not selected_cluster_id
            else 'Selected cluster is not available for live worker capacity metrics.'
        )

    try:
        from app.analytics.capacity.service import CapacityService
        from app.analytics.utilization.service import UtilizationService
        from app.prometheus.service import PrometheusService

        prometheus = PrometheusService(live_cluster)
        capacity_service = CapacityService(UtilizationService(prometheus))
        summary = capacity_service.get_capacity_summary_from_summary({})
    except Exception as exc:
        return empty_capacity_snapshot(insight=f'Prometheus worker capacity snapshot unavailable: {exc}')

    cpu = _worker_capacity_item(
        label='CPU',
        section=summary.get('cpu', {}),
        unit='cores',
        digits=2,
    )
    memory = _worker_capacity_item(
        label='Memory',
        section=summary.get('memory', {}),
        unit='GiB',
        digits=2,
    )
    pods = _worker_capacity_item(
        label='Pod Capacity',
        section=summary.get('pods', {}),
        unit='pods',
        digits=0,
    )
    items = [cpu, memory, pods]

    measured_items = [item for item in items if item.used_percent is not None]
    highest = max(measured_items, key=lambda item: safe_float(item.used_percent), default=None)
    risk = risk_from_percent(safe_float(highest.used_percent)) if highest is not None else 'Unknown'
    insight = capacity_insight(risk, items)
    risk_detail, recommended_action = _capacity_risk_guidance(risk, highest)

    return CapacitySnapshot(
        items=items,
        risk=risk,
        insight=insight,
        risk_detail=risk_detail,
        recommended_action=recommended_action,
        source_status='Available',
    )


def _worker_capacity_item(
    *,
    label: str,
    section: dict[str, Any],
    unit: str,
    digits: int,
) -> CapacityItem:
    capacity = safe_float(section.get('capacity'))
    used = safe_float(section.get('used'))
    headroom = safe_optional_float(section.get('headroom')) if capacity > 0 else None
    used_percent = max(0.0, min(100.0, 100.0 - headroom)) if headroom is not None else None

    if digits == 0:
        description = f'{int(round(used))} / {int(round(capacity))} {unit} on worker nodes'
    else:
        description = f'{used:.{digits}f} / {capacity:.{digits}f} worker allocatable {unit}'

    return CapacityItem(
        label=label,
        used_percent=round(used_percent, 2) if used_percent is not None else None,
        headroom_percent=round(headroom, 2) if headroom is not None else None,
        description=description,
    )


def empty_capacity_snapshot(*, insight: str) -> CapacitySnapshot:
    return CapacitySnapshot(
        items=[
            CapacityItem(
                label='CPU', used_percent=None, headroom_percent=None, description='Worker metric unavailable'
            ),
            CapacityItem(
                label='Memory', used_percent=None, headroom_percent=None, description='Worker metric unavailable'
            ),
            CapacityItem(
                label='Pod Capacity', used_percent=None, headroom_percent=None, description='Worker metric unavailable'
            ),
        ],
        risk='Unknown',
        insight=insight,
        risk_detail='Overall worker capacity risk cannot be calculated because one or more required metrics are unavailable.',
        recommended_action='Verify the selected cluster Prometheus connection and kube-state-metrics node-role labels, then reload the snapshot.',
        source_status='Unavailable',
    )


def _capacity_risk_guidance(
    risk: str,
    highest: CapacityItem | None,
) -> tuple[str, str]:
    resource = highest.label if highest is not None else 'Worker capacity'
    utilization = safe_float(highest.used_percent) if highest is not None else 0.0

    if risk == 'Critical':
        return (
            f'{resource} utilization is {utilization:.0f}%, leaving almost no worker-node scheduling buffer. '
            'New pods may remain Pending and existing workloads may face eviction or performance degradation.',
            'Review Capacity Analysis and Top Consumers immediately, reduce avoidable load, and add or resize worker capacity before the remaining headroom is exhausted.',
        )
    if risk == 'High':
        return (
            f'{resource} utilization is {utilization:.0f}%. Worker-node headroom is limited and sustained growth can affect scheduling reliability.',
            'Review top consumers, requests and limits, forecast trend, and pending workloads. Prepare scaling or workload optimization before utilization reaches the critical threshold.',
        )
    if risk == 'Medium':
        return (
            f'{resource} utilization is {utilization:.0f}%. Capacity remains usable, but the operational buffer is narrowing.',
            'Validate workload requests and limits, monitor the growth trend, and confirm that planned deployments fit within current worker headroom.',
        )
    if risk == 'Low':
        return (
            f'{resource} is the highest worker-node signal at {utilization:.0f}%, with sufficient headroom for current demand.',
            'No immediate scaling action is required. Continue monitoring trends and keep workload requests, limits, and capacity baselines current.',
        )
    return (
        'Worker capacity risk is unknown because the required utilization or allocatable metrics are incomplete.',
        'Verify Prometheus, kube-state-metrics, and node-role labels before making scaling or placement decisions.',
    )
