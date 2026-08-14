from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.kubernetes.resources.common import format_age
from app.inventory.kubernetes.resources.pod_detail import build_pod_detail
from app.inventory.kubernetes.resources.pod_semantics import OPERATIONAL_STATE_TONES, pod_operational_state, pod_ready_values
from app.models import Cluster, PodInventory

UNKNOWN_FILTER = '__unknown__'
UNSCHEDULED_FILTER = '__unscheduled__'


def _blank_or_null(column):
    return or_(column.is_(None), func.trim(column) == '')


def _apply_pod_filters(
    query,
    *,
    cluster_id: str | None = None,
    namespace: str | None = None,
    status: str | None = None,
    owner_type: str | None = None,
    node: str | None = None,
    search: str | None = None,
):
    if cluster_id:
        query = query.filter(PodInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(PodInventory.namespace == namespace)
    if status == UNKNOWN_FILTER:
        query = query.filter(_blank_or_null(PodInventory.phase))
    elif status:
        query = query.filter(PodInventory.phase == status)
    if owner_type == 'Standalone':
        query = query.filter(_blank_or_null(PodInventory.workload_type))
    elif owner_type:
        query = query.filter(PodInventory.workload_type == owner_type)
    if node == UNSCHEDULED_FILTER:
        query = query.filter(_blank_or_null(PodInventory.node_name))
    elif node:
        query = query.filter(PodInventory.node_name == node)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                PodInventory.pod_name.ilike(pattern),
                PodInventory.pod_ip.ilike(pattern),
                PodInventory.workload_type.ilike(pattern),
                PodInventory.workload_name.ilike(pattern),
                PodInventory.node_name.ilike(pattern),
            )
        )
    return query


def get_pod_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(PodInventory.namespace), PodInventory)
    query = _apply_pod_filters(query, cluster_id=cluster_id)
    rows = query.distinct().order_by(PodInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_pod_filter_owner_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    owner_expression = func.coalesce(func.nullif(func.trim(PodInventory.workload_type), ''), 'Standalone')
    query = filter_current_generation(db.session.query(owner_expression), PodInventory)
    query = _apply_pod_filters(query, cluster_id=cluster_id, namespace=namespace)
    rows = query.distinct().order_by(owner_expression).all()
    return [str(row[0]) for row in rows if row[0]]


def get_pod_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    owner_type: str | None = None,
) -> list[dict[str, str]]:
    query = filter_current_generation(db.session.query(PodInventory.phase), PodInventory)
    query = _apply_pod_filters(query, cluster_id=cluster_id, namespace=namespace, owner_type=owner_type)
    rows = query.distinct().order_by(PodInventory.phase).all()
    phases = [str(row[0]) for row in rows if row[0] and str(row[0]).strip()]
    options = [{'value': phase, 'label': phase} for phase in phases]
    if any(not row[0] or not str(row[0]).strip() for row in rows):
        options.append({'value': UNKNOWN_FILTER, 'label': 'Unknown'})
    return options


def get_pod_filter_nodes(
    cluster_id: str | None = None,
    namespace: str | None = None,
    owner_type: str | None = None,
) -> list[dict[str, str]]:
    query = filter_current_generation(db.session.query(PodInventory.node_name), PodInventory)
    query = _apply_pod_filters(query, cluster_id=cluster_id, namespace=namespace, owner_type=owner_type)
    rows = query.distinct().order_by(PodInventory.node_name).all()
    options = [{'value': str(row[0]), 'label': str(row[0])} for row in rows if row[0] and str(row[0]).strip()]
    if any(not row[0] or not str(row[0]).strip() for row in rows):
        options.insert(0, {'value': UNSCHEDULED_FILTER, 'label': 'Not Scheduled'})
    return options


def _pod_container_count(pod: PodInventory) -> int:
    configuration = (pod.details or {}).get('configuration') or {}
    configured_count = configuration.get('container_count')
    if configured_count is not None:
        try:
            return int(configured_count)
        except (TypeError, ValueError):
            pass
    if pod.container_names:
        return len(pod.container_names)
    ready_values = pod_ready_values(pod.ready)
    return ready_values[1] if ready_values else 0


def _overall_posture(total: int, counts: dict[str, int]) -> tuple[str, str]:
    if total == 0:
        return 'No Data', 'unknown'
    if counts.get('Failed', 0) > 0:
        return 'Critical', 'critical'
    if counts.get('Not Ready', 0) > 0 or counts.get('Terminating', 0) > 0:
        return 'Attention', 'warning'
    if counts.get('Starting', 0) > 0:
        return 'Progressing', 'pending'
    if counts.get('Unknown', 0) > 0:
        return 'Review Required', 'warning'
    if counts.get('Ready', 0) == 0 and counts.get('Completed', 0) > 0:
        return 'Completed', 'info'
    return 'Stable', 'normal'


def _base_pod_query():
    query = db.session.query(
        PodInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == PodInventory.cluster_id)
    return filter_current_generation(query, PodInventory)


def _pod_summary(query) -> dict[str, Any]:
    rows = (
        query.with_entities(
            PodInventory.phase,
            PodInventory.ready,
            func.count(PodInventory.id),
            func.sum(case((PodInventory.restart_count > 0, 1), else_=0)),
            func.coalesce(func.sum(PodInventory.image_count), 0),
        )
        .group_by(PodInventory.phase, PodInventory.ready)
        .all()
    )
    state_counts = {state: 0 for state in OPERATIONAL_STATE_TONES}
    status_counts: dict[str, int] = {}
    restart_activity = 0
    total_image_references = 0
    for phase, ready, count, restarted_count, image_count in rows:
        state_label, _, _ = pod_operational_state(phase, ready)
        state_counts[state_label] += int(count or 0)
        phase_label = str(phase or 'Unknown')
        status_counts[phase_label] = status_counts.get(phase_label, 0) + int(count or 0)
        restart_activity += int(restarted_count or 0)
        total_image_references += int(image_count or 0)
    return {
        'state_counts': state_counts,
        'status_counts': status_counts,
        'restart_activity': restart_activity,
        'total_image_references': total_image_references,
    }


def _unique_image_count(query) -> int:
    unique_images: set[str] = set()
    for container_images, init_container_images in query.with_entities(
        PodInventory.container_images,
        PodInventory.init_container_images,
    ).all():
        unique_images.update(container_images or [])
        unique_images.update(init_container_images or [])
    return len(unique_images)


def _pod_list_row(pod: PodInventory, cluster_name: str, cluster_environment: str) -> dict[str, Any]:
    operational_state, state_tone, state_evidence = pod_operational_state(pod.phase, pod.ready)
    ready_values = pod_ready_values(pod.ready)
    container_count = _pod_container_count(pod)
    details = pod.details or {}
    runtime_evidence_reported = bool(details.get('runtime_evidence_reported', pod.ready not in {None, 'Not Reported'}))
    specification_evidence_reported = bool(
        details.get(
            'specification_evidence_reported',
            bool(details.get('configuration') or details.get('placement') or details.get('volumes')),
        )
    )
    owner_display = (
        f'{pod.workload_type} · {pod.workload_name}' if pod.workload_type and pod.workload_name else 'Standalone'
    )
    restart_count = int(pod.restart_count or 0)
    return {
        'id': pod.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': pod.namespace,
        'name': pod.pod_name,
        'node': pod.node_name,
        'ready': pod.ready or 'Not Reported',
        'ready_count': ready_values[0] if ready_values else 0,
        'ready_total': ready_values[1] if ready_values else 0,
        'restarts': restart_count,
        'ip': pod.pod_ip,
        'status': pod.phase or 'Unknown',
        'operational_state_label': operational_state,
        'operational_state_tone': state_tone,
        'state_evidence': state_evidence,
        'owner_type': pod.workload_type or 'Standalone',
        'owner_name': pod.workload_name or 'Not Reported',
        'owner_display': owner_display,
        'container_count': container_count if specification_evidence_reported else None,
        'identity_supporting': (
            f'{container_count} Container' + ('s' if container_count != 1 else '')
            if specification_evidence_reported
            else 'Container Specification Not Reported'
        )
        + f' · Age {format_age(pod.created_at)}',
        'placement_primary': pod.node_name or 'Not Scheduled',
        'placement_secondary': pod.pod_ip or 'Pod IP Not Reported',
        'activity_secondary': (
            f'{restart_count} Restart' + ('' if restart_count == 1 else 's')
            if runtime_evidence_reported
            else 'Restart Evidence Not Reported'
        ),
    }


def get_pod_inventory(
    cluster_id=None,
    namespace=None,
    status=None,
    owner_type=None,
    node=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = _apply_pod_filters(
        _base_pod_query(),
        cluster_id=cluster_id,
        namespace=namespace,
        status=status,
        owner_type=owner_type,
        node=node,
        search=search,
    )
    summary = _pod_summary(query)
    owner_type_count = (
        query.with_entities(
            func.count(
                func.distinct(func.coalesce(func.nullif(func.trim(PodInventory.workload_type), ''), 'Standalone'))
            )
        ).scalar()
        or 0
    )
    rows, pagination = paginate_query(
        query.order_by(Cluster.name, PodInventory.namespace, PodInventory.pod_name),
        page=page,
        per_page=per_page,
    )
    pods = [_pod_list_row(pod, cluster_name, environment) for pod, cluster_name, environment in rows]
    total_pods = pagination['total_items']
    counts = summary['state_counts']
    overall_posture, overall_tone = _overall_posture(total_pods, counts)
    return {
        'total_pods': total_pods,
        'ready_count': counts['Ready'],
        'exception_count': (
            counts['Starting'] + counts['Not Ready'] + counts['Terminating'] + counts['Failed'] + counts['Unknown']
        ),
        'starting_count': counts['Starting'],
        'not_ready_count': counts['Not Ready'],
        'terminating_count': counts['Terminating'],
        'failed_count': counts['Failed'],
        'completed_count': counts['Completed'],
        'unknown_count': counts['Unknown'],
        'restart_activity': summary['restart_activity'],
        'unique_image_count': _unique_image_count(query),
        'total_image_references': summary['total_image_references'],
        'owner_type_count': int(owner_type_count),
        'overall_posture': overall_posture,
        'overall_posture_tone': overall_tone,
        'scope_label': 'All Clusters',
        'status_counts': summary['status_counts'],
        'pods': pods,
        'pagination': pagination,
    }


def get_pod_detail(pod_id: int) -> dict[str, Any] | None:
    result = _base_pod_query().filter(PodInventory.id == pod_id).first()
    if result is None:
        return None
    pod, cluster_name, cluster_environment = result
    return build_pod_detail(pod, cluster_name, cluster_environment)
