from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.analytics.common.base_service import raw_percent, safe_round
from app.analytics.top_consumers.contracts import RESOURCE_ICONS, RESOURCE_LABELS
from app.analytics.top_consumers.evidence import (
    ScalarEvidence,
    VectorEvidence,
    metric_label,
    sample_metric,
    sample_value,
)


@dataclass(frozen=True, slots=True)
class ConsumerRowSpec:
    identity: dict[str, str]
    namespace: str
    resource_type: str
    current_usage: float
    current_display: str
    total_usage: ScalarEvidence
    request: float
    request_display: str
    limit: float
    limit_display: str
    request_utilization: float | None
    limit_utilization: float | None
    pressure_percent: float | None
    pressure_basis: str
    risk: dict[str, str]
    recommendation: str
    pod: str = ''
    container: str = ''
    workload_owner: str = ''
    workload_owner_kind: str = ''
    pvc_name: str = ''
    request_evidence_available: bool = False
    limit_evidence_available: bool = False
    denominator_evidence_available: bool = False


def build_owner_map(evidence: VectorEvidence) -> dict[str, dict[str, str]]:
    owners: dict[str, dict[str, str]] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        namespace = metric_label(metric, 'namespace')
        pod = metric_label(metric, 'pod')
        owner_name = metric_label(metric, 'owner_name')
        if not namespace or not pod or not owner_name:
            continue
        candidate = {
            'name': owner_name,
            'kind': metric_label(metric, 'owner_kind') or 'Workload',
            'controller': metric_label(metric, 'owner_is_controller'),
        }
        key = pod_key(namespace, pod)
        current = owners.get(key)
        if current is None or candidate['controller'].lower() == 'true':
            owners[key] = candidate
    return owners


def build_compute_rows(
    *,
    usage: VectorEvidence,
    requests: VectorEvidence,
    limits: VectorEvidence,
    owner_map: dict[str, dict[str, str]],
    resource_type: str,
    scope_total: ScalarEvidence,
) -> list[dict[str, Any]]:
    request_map = vector_value_map(requests, key_builder=container_key)
    limit_map = vector_value_map(limits, key_builder=container_key)
    rows: list[dict[str, Any]] = []
    for item in usage.rows:
        metric = sample_metric(item)
        namespace = metric_label(metric, 'namespace')
        pod = metric_label(metric, 'pod')
        container = metric_label(metric, 'container')
        current = sample_value(item)
        if not namespace or not pod or not container or current is None:
            continue
        key = container_key(metric)
        request = request_map.get(key, 0.0)
        limit = limit_map.get(key, 0.0)
        request_utilization = raw_percent(current, request) if request > 0 else None
        limit_utilization = raw_percent(current, limit) if limit > 0 else None
        pressure_values = [
            value
            for value in (request_utilization, limit_utilization)
            if value is not None
        ]
        pressure = max(pressure_values) if pressure_values else None
        risk = compute_risk(
            resource_type=resource_type,
            request=request,
            limit=limit,
            request_observed=requests.observed,
            limit_observed=limits.observed,
            request_utilization=request_utilization,
            limit_utilization=limit_utilization,
        )
        owner = owner_map.get(pod_key(namespace, pod), {})
        identity = build_compute_identity(
            namespace=namespace,
            pod=pod,
            container=container,
            owner_name=str(owner.get('name') or ''),
            owner_kind=str(owner.get('kind') or ''),
        )
        rows.append(
            build_consumer_row(
                ConsumerRowSpec(
                    identity=identity,
                    namespace=namespace,
                    resource_type=resource_type,
                    current_usage=current,
                    current_display=(
                        format_cpu(current)
                        if resource_type == 'cpu'
                        else format_bytes(current)
                    ),
                    total_usage=scope_total,
                    request=request,
                    request_display=format_resource_value(
                        resource_type,
                        request,
                        available=requests.observed and request > 0,
                    ),
                    limit=limit,
                    limit_display=format_resource_value(
                        resource_type,
                        limit,
                        available=limits.observed and limit > 0,
                    ),
                    request_utilization=request_utilization,
                    limit_utilization=limit_utilization,
                    pressure_percent=pressure,
                    pressure_basis='Request / Limit',
                    risk=risk,
                    recommendation=resource_recommendation(
                        resource_type=resource_type,
                        pressure_percent=pressure,
                        request=request,
                        limit=limit,
                        request_observed=requests.observed,
                        limit_observed=limits.observed,
                    ),
                    pod=pod,
                    container=container,
                    workload_owner=str(owner.get('name') or ''),
                    workload_owner_kind=str(owner.get('kind') or ''),
                    request_evidence_available=requests.observed,
                    limit_evidence_available=limits.observed,
                    denominator_evidence_available=(
                        requests.observed or limits.observed
                    ),
                )
            )
        )
    return rows


def build_pod_rows(
    *,
    usage: VectorEvidence,
    scope_total: ScalarEvidence,
    capacity: ScalarEvidence,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in usage.rows:
        metric = sample_metric(item)
        namespace = metric_label(metric, 'namespace')
        current = sample_value(item)
        if not namespace or current is None:
            continue
        pressure = (
            raw_percent(current, capacity.value)
            if capacity.available and capacity.value > 0
            else None
        )
        rows.append(
            build_consumer_row(
                ConsumerRowSpec(
                    identity={
                        'entity_type': 'namespace',
                        'entity_label': 'Namespace',
                        'icon': 'folder-tree',
                        'primary': namespace,
                        'secondary': 'Namespace Running Pod Density',
                        'tertiary': '',
                    },
                    namespace=namespace,
                    resource_type='pods',
                    current_usage=current,
                    current_display=f'{int(current)} Pods',
                    total_usage=scope_total,
                    request=0,
                    request_display='N/A',
                    limit=capacity.value,
                    limit_display=(
                        f'{int(capacity.value)} Pods'
                        if capacity.available and capacity.value > 0
                        else 'N/A'
                    ),
                    request_utilization=None,
                    limit_utilization=None,
                    pressure_percent=pressure,
                    pressure_basis='Ready Worker Pod Capacity',
                    risk=ratio_risk(pressure),
                    recommendation=resource_recommendation(
                        resource_type='pods',
                        pressure_percent=pressure,
                        request=0,
                        limit=capacity.value,
                        request_observed=True,
                        limit_observed=capacity.available,
                    ),
                    limit_evidence_available=capacity.available,
                    denominator_evidence_available=capacity.available,
                )
            )
        )
    return rows


def build_pvc_rows(
    *,
    usage: VectorEvidence,
    capacity: VectorEvidence,
    scope_total: ScalarEvidence,
) -> list[dict[str, Any]]:
    capacity_map = vector_value_map(capacity, key_builder=pvc_key)
    rows: list[dict[str, Any]] = []
    for item in usage.rows:
        metric = sample_metric(item)
        namespace = metric_label(metric, 'namespace')
        claim = metric_label(metric, 'persistentvolumeclaim')
        current = sample_value(item)
        if not namespace or not claim or current is None:
            continue
        denominator = capacity_map.get(pvc_key(metric))
        denominator_available = denominator is not None and denominator > 0
        pressure = (
            raw_percent(current, denominator)
            if denominator_available and denominator is not None
            else None
        )
        rows.append(
            build_consumer_row(
                ConsumerRowSpec(
                    identity={
                        'entity_type': 'pvc',
                        'entity_label': 'PersistentVolumeClaim',
                        'icon': 'database',
                        'primary': claim,
                        'secondary': namespace,
                        'tertiary': 'PersistentVolumeClaim',
                    },
                    namespace=namespace,
                    resource_type='pvc',
                    current_usage=current,
                    current_display=format_bytes(current),
                    total_usage=scope_total,
                    request=0,
                    request_display='N/A',
                    limit=denominator or 0.0,
                    limit_display=(
                        format_bytes(denominator)
                        if denominator_available and denominator is not None
                        else 'N/A'
                    ),
                    request_utilization=None,
                    limit_utilization=None,
                    pressure_percent=pressure,
                    pressure_basis='Observed Volume Capacity',
                    risk=ratio_risk(pressure),
                    recommendation=resource_recommendation(
                        resource_type='pvc',
                        pressure_percent=pressure,
                        request=0,
                        limit=denominator or 0.0,
                        request_observed=True,
                        limit_observed=denominator_available,
                    ),
                    pvc_name=claim,
                    limit_evidence_available=denominator_available,
                    denominator_evidence_available=denominator_available,
                )
            )
        )
    return rows


def build_consumer_row(spec: ConsumerRowSpec) -> dict[str, Any]:
    contribution = (
        raw_percent(spec.current_usage, spec.total_usage.value)
        if spec.total_usage.available and spec.total_usage.value > 0
        else None
    )
    return {
        'rank': 0,
        'identity': spec.identity,
        'entity_type': spec.identity.get('entity_type', 'consumer'),
        'namespace': spec.namespace,
        'workload': spec.workload_owner or spec.identity.get('primary', '-'),
        'workload_owner': spec.workload_owner,
        'workload_owner_kind': spec.workload_owner_kind,
        'pod': spec.pod,
        'container': spec.container,
        'pvc_name': spec.pvc_name,
        'resource_type': spec.resource_type,
        'resource_label': RESOURCE_LABELS.get(
            spec.resource_type,
            spec.resource_type.title(),
        ),
        'resource_icon': RESOURCE_ICONS.get(spec.resource_type, 'activity'),
        'current_usage': spec.current_usage,
        'current_display': spec.current_display,
        'scope_total': spec.total_usage.value,
        'scope_total_available': spec.total_usage.available,
        'contribution_percent': rounded_percent(contribution),
        'contribution_display': percent_display(contribution),
        'contribution_bar_percent': bar_percent(contribution),
        'request': spec.request,
        'request_display': spec.request_display,
        'limit': spec.limit,
        'limit_display': spec.limit_display,
        'request_utilization': rounded_percent(spec.request_utilization),
        'request_utilization_display': percent_display(
            spec.request_utilization
        ),
        'limit_utilization': rounded_percent(spec.limit_utilization),
        'limit_utilization_display': percent_display(spec.limit_utilization),
        'pressure_percent': rounded_percent(spec.pressure_percent),
        'pressure_display': percent_display(spec.pressure_percent),
        'pressure_bar_percent': bar_percent(spec.pressure_percent),
        'pressure_basis': spec.pressure_basis,
        'pressure_available': spec.pressure_percent is not None,
        'denominator_evidence_available': (
            spec.denominator_evidence_available
        ),
        'request_evidence_available': spec.request_evidence_available,
        'limit_evidence_available': spec.limit_evidence_available,
        'risk': spec.risk,
        'recommendation': spec.recommendation,
        'request_state': request_state(
            spec.request,
            spec.resource_type,
            evidence_available=spec.request_evidence_available,
        ),
        'limit_state': limit_state(
            spec.limit,
            spec.resource_type,
            evidence_available=spec.limit_evidence_available,
        ),
    }


def semantic_state(key: str, label: str | None = None) -> dict[str, str]:
    labels = {
        'critical': 'Critical',
        'warning': 'Warning',
        'info': 'Info',
        'normal': 'Normal',
        'unknown': 'Unknown',
    }
    normalized = key if key in labels else 'unknown'
    return {
        'key': normalized,
        'label': label or labels[normalized],
        'tone': normalized,
    }


def ratio_risk(percent: float | None) -> dict[str, str]:
    if percent is None:
        return semantic_state('unknown')
    if percent >= 90:
        return semantic_state('critical')
    if percent >= 75:
        return semantic_state('warning')
    return semantic_state('normal')


def compute_risk(
    *,
    resource_type: str,
    request: float,
    limit: float,
    request_observed: bool,
    limit_observed: bool,
    request_utilization: float | None,
    limit_utilization: float | None,
) -> dict[str, str]:
    if request_observed and request <= 0:
        return semantic_state('critical', 'Request Missing')
    highest = max(
        [
            value
            for value in (request_utilization, limit_utilization)
            if value is not None
        ],
        default=None,
    )
    if highest is not None and highest >= 90:
        return semantic_state('critical')
    if highest is not None and highest >= 75:
        return semantic_state('warning')
    if limit_observed and resource_type == 'memory' and limit <= 0:
        return semantic_state('warning', 'Memory Limit Missing')
    if limit_observed and resource_type == 'cpu' and limit <= 0:
        return semantic_state('info', 'CPU Limit Unset')
    if not request_observed or not limit_observed:
        return semantic_state('unknown', 'Evidence Incomplete')
    return semantic_state('normal')


def request_state(
    request: float,
    resource_type: str,
    *,
    evidence_available: bool,
) -> dict[str, str]:
    if resource_type not in {'cpu', 'memory'}:
        return semantic_state('unknown', 'Not Applicable')
    if not evidence_available:
        return semantic_state('unknown', 'Evidence Unavailable')
    return (
        semantic_state('normal', 'Configured')
        if request > 0
        else semantic_state('critical', 'Missing')
    )


def limit_state(
    limit: float,
    resource_type: str,
    *,
    evidence_available: bool,
) -> dict[str, str]:
    if resource_type not in {'cpu', 'memory'}:
        return semantic_state('unknown', 'Not Applicable')
    if not evidence_available:
        return semantic_state('unknown', 'Evidence Unavailable')
    if resource_type == 'cpu':
        return (
            semantic_state('normal', 'Configured')
            if limit > 0
            else semantic_state('info', 'Intentionally Unset / Review Policy')
        )
    return (
        semantic_state('normal', 'Configured')
        if limit > 0
        else semantic_state('warning', 'Missing')
    )


def resource_recommendation(
    *,
    resource_type: str,
    pressure_percent: float | None,
    request: float,
    limit: float,
    request_observed: bool,
    limit_observed: bool,
) -> str:
    if resource_type == 'pvc':
        if not limit_observed or pressure_percent is None:
            return 'Restore observed PVC capacity evidence'
        if pressure_percent >= 90:
            return 'Clean up or expand PVC capacity'
        if pressure_percent >= 75:
            return 'Plan PVC expansion and review retention'
        return 'Monitor claim growth'
    if resource_type == 'pods':
        if not limit_observed or pressure_percent is None:
            return 'Restore Ready-worker pod-capacity evidence'
        if pressure_percent >= 75:
            return 'Review pod density and Ready-worker capacity'
        return 'Monitor namespace pod growth'
    if not request_observed:
        return 'Restore request evidence before right-sizing'
    if request <= 0:
        return 'Add CPU request' if resource_type == 'cpu' else 'Add memory request'
    if not limit_observed:
        return 'Restore limit evidence before policy review'
    if resource_type == 'memory' and limit <= 0:
        return 'Review missing memory limit coverage'
    if pressure_percent is not None and pressure_percent >= 90:
        return 'Review scaling and resource boundaries immediately'
    if pressure_percent is not None and pressure_percent >= 75:
        return 'Validate demand and right-size resource boundaries'
    if resource_type == 'cpu' and limit <= 0:
        return 'Validate intentional CPU limit policy'
    return 'Continue monitoring consumption and contribution'


def build_compute_identity(
    *,
    namespace: str,
    pod: str,
    container: str,
    owner_name: str,
    owner_kind: str,
) -> dict[str, str]:
    if owner_name:
        return {
            'entity_type': 'container',
            'entity_label': 'Workload Owner',
            'icon': 'boxes',
            'primary': owner_name,
            'secondary': f'{owner_kind or "Workload"} · {namespace}',
            'tertiary': f'{pod} · {container}',
        }
    return {
        'entity_type': 'container',
        'entity_label': 'Pod',
        'icon': 'container',
        'primary': pod,
        'secondary': namespace,
        'tertiary': container,
    }


def vector_value_map(
    evidence: VectorEvidence,
    *,
    key_builder: Callable[[dict[str, Any]], str],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in evidence.rows:
        metric = sample_metric(item)
        key = key_builder(metric)
        value = sample_value(item)
        if key and value is not None:
            values[key] = max(values.get(key, value), value)
    return values


def container_key(metric: dict[str, Any]) -> str:
    namespace = metric_label(metric, 'namespace')
    pod = metric_label(metric, 'pod')
    container = metric_label(metric, 'container')
    return f'{namespace}/{pod}/{container}' if namespace and pod and container else ''


def pvc_key(metric: dict[str, Any]) -> str:
    namespace = metric_label(metric, 'namespace')
    claim = metric_label(metric, 'persistentvolumeclaim')
    return f'{namespace}/{claim}' if namespace and claim else ''


def pod_key(namespace: str, pod: str) -> str:
    return f'{namespace}/{pod}'


def rounded_percent(value: float | None) -> float | None:
    return safe_round(value, 1) if value is not None else None


def percent_display(value: float | None) -> str:
    return f'{safe_round(value, 1)}%' if value is not None else 'N/A'


def bar_percent(value: float | None) -> float:
    if value is None:
        return 0
    return min(max(safe_round(value, 1), 0), 100)


def format_cpu(value: float) -> str:
    return f'{safe_round(value, 2)} cores'


def format_bytes(value: float) -> str:
    if value <= 0:
        return '0 B'
    units = ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB')
    size = float(value)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return (
        f'{size:.0f} {units[unit_index]}'
        if unit_index == 0
        else f'{size:.2f} {units[unit_index]}'
    )


def format_resource_value(
    resource_type: str,
    value: float,
    *,
    available: bool,
) -> str:
    if not available:
        return 'N/A'
    return format_cpu(value) if resource_type == 'cpu' else format_bytes(value)
