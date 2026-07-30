from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import _display_boolean, format_age
from app.models import Cluster, PodInventory


_OPERATIONAL_STATE_TONES = {
    'Ready': 'normal',
    'Starting': 'pending',
    'Not Ready': 'warning',
    'Failed': 'critical',
    'Completed': 'info',
    'Unknown': 'unknown',
}


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
    if status:
        query = query.filter(PodInventory.phase == status)
    if owner_type == 'Standalone':
        query = query.filter(PodInventory.workload_type.is_(None))
    elif owner_type:
        query = query.filter(PodInventory.workload_type == owner_type)
    if node:
        query = query.filter(PodInventory.node_name == node)
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            or_(
                PodInventory.pod_name.ilike(pattern),
                PodInventory.pod_ip.ilike(pattern),
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
    owner_expression = func.coalesce(PodInventory.workload_type, 'Standalone')
    query = filter_current_generation(db.session.query(owner_expression), PodInventory)
    query = _apply_pod_filters(query, cluster_id=cluster_id, namespace=namespace)
    rows = query.distinct().order_by(owner_expression).all()
    return [str(row[0]) for row in rows if row[0]]


def get_pod_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    owner_type: str | None = None,
) -> list[str]:
    query = filter_current_generation(db.session.query(PodInventory.phase), PodInventory)
    query = _apply_pod_filters(
        query,
        cluster_id=cluster_id,
        namespace=namespace,
        owner_type=owner_type,
    )
    rows = query.distinct().order_by(PodInventory.phase).all()
    return [row[0] for row in rows if row[0]]


def get_pod_filter_nodes(
    cluster_id: str | None = None,
    namespace: str | None = None,
    owner_type: str | None = None,
) -> list[str]:
    query = db.session.query(PodInventory.node_name).filter(
        PodInventory.node_name.is_not(None),
        PodInventory.node_name != '',
    )
    query = filter_current_generation(query, PodInventory)
    query = _apply_pod_filters(
        query,
        cluster_id=cluster_id,
        namespace=namespace,
        owner_type=owner_type,
    )
    rows = query.distinct().order_by(PodInventory.node_name).all()
    return [row[0] for row in rows if row[0]]


def _pod_container_count(pod: PodInventory) -> int:
    details = pod.details or {}
    configuration = details.get('configuration') or {}
    configured_count = configuration.get('container_count')
    if configured_count is not None:
        try:
            return int(configured_count)
        except (TypeError, ValueError):
            pass
    if pod.container_names:
        return len(pod.container_names)
    _, ready_total = _pod_ready_values(pod.ready)
    return ready_total


def _pod_ready_values(value: str | None) -> tuple[int, int]:
    if not value or '/' not in value:
        return 0, 0
    ready, total = value.split('/', maxsplit=1)
    try:
        return int(ready), int(total)
    except (TypeError, ValueError):
        return 0, 0


def _pod_operational_state(phase: str | None, ready: str | None) -> tuple[str, str, str]:
    phase_label = str(phase or 'Unknown')
    ready_count, ready_total = _pod_ready_values(ready)
    normalized_phase = phase_label.casefold()

    if normalized_phase == 'failed':
        state = 'Failed'
    elif normalized_phase == 'pending':
        state = 'Starting'
    elif normalized_phase == 'succeeded':
        state = 'Completed'
    elif normalized_phase == 'running':
        state = 'Ready' if ready_total > 0 and ready_count == ready_total else 'Not Ready'
    else:
        state = 'Unknown'

    evidence = phase_label
    if ready_total > 0:
        evidence = f'{phase_label} · {ready_count}/{ready_total} Ready'
    return state, _OPERATIONAL_STATE_TONES[state], evidence


def _overall_posture(total: int, counts: dict[str, int]) -> tuple[str, str]:
    if total == 0:
        return 'No Data', 'unknown'
    if counts.get('Failed', 0) > 0:
        return 'Critical', 'critical'
    if counts.get('Not Ready', 0) > 0:
        return 'Attention', 'warning'
    if counts.get('Starting', 0) > 0:
        return 'Progressing', 'pending'
    if counts.get('Unknown', 0) > 0:
        return 'Review Required', 'warning'
    if counts.get('Ready', 0) == 0 and counts.get('Completed', 0) > 0:
        return 'Completed', 'info'
    return 'Stable', 'normal'


def _parse_inventory_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _condition_presentation(condition: dict[str, Any]) -> dict[str, Any]:
    condition_type = str(condition.get('type') or 'Unknown')
    status = str(condition.get('status') or 'Unknown')
    reason = str(condition.get('reason') or '').strip() or None
    normalized_type = condition_type.casefold()
    normalized_status = status.casefold()

    if normalized_type in {'ready', 'containersready'}:
        label = 'Ready' if normalized_status == 'true' else ('Not Ready' if normalized_status == 'false' else 'Unknown')
        tone = 'normal' if normalized_status == 'true' else ('warning' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'podscheduled':
        label = 'Scheduled' if normalized_status == 'true' else ('Pending' if normalized_status == 'false' else 'Unknown')
        tone = 'normal' if normalized_status == 'true' else ('pending' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'initialized':
        label = 'Initialized' if normalized_status == 'true' else ('Starting' if normalized_status == 'false' else 'Unknown')
        tone = 'normal' if normalized_status == 'true' else ('pending' if normalized_status == 'false' else 'unknown')
    elif normalized_type == 'disruptiontarget':
        label = 'Disruption Target' if normalized_status == 'true' else 'Not Targeted'
        tone = 'warning' if normalized_status == 'true' else 'normal'
    else:
        label = status
        tone = 'unknown'

    return {
        'type': condition_type,
        'status': status,
        'state_label': label,
        'state_tone': tone,
        'reason': reason,
        'message': condition.get('message'),
        'last_transition_time': _parse_inventory_datetime(condition.get('last_transition_time')),
    }


def _container_presentation(container: dict[str, Any]) -> dict[str, Any]:
    kind = str(container.get('kind') or 'Regular')
    state = str(container.get('state') or 'Unknown')
    normalized_state = state.casefold()
    exit_code = container.get('exit_code')
    ready = bool(container.get('ready'))

    if normalized_state == 'running':
        label = 'Ready' if ready else 'Not Ready'
        tone = 'normal' if ready else 'warning'
    elif normalized_state == 'waiting':
        label = 'Waiting'
        tone = 'pending'
    elif normalized_state == 'terminated':
        if exit_code in (0, '0'):
            label = 'Completed'
            tone = 'info'
        else:
            label = 'Failed'
            tone = 'critical'
    elif normalized_state in {'not reported', 'unknown'}:
        label = 'Unknown'
        tone = 'unknown'
    else:
        label = state
        tone = 'unknown'

    result = dict(container)
    result.update(
        {
            'kind': kind,
            'runtime_state_label': label,
            'runtime_state_tone': tone,
            'started_at_value': _parse_inventory_datetime(container.get('started_at')),
            'finished_at_value': _parse_inventory_datetime(container.get('finished_at')),
            'restart_activity': f"{int(container.get('restart_count') or 0)} Restart" + (
                '' if int(container.get('restart_count') or 0) == 1 else 's'
            ),
        }
    )
    return result


def _operational_context(
    state_label: str,
    restart_count: int,
    container_statuses: list[dict[str, Any]],
) -> dict[str, str]:
    if state_label == 'Failed':
        return {
            'title': 'Investigate Pod Failure',
            'description': 'Review container exit codes, image delivery, volume mounts, placement constraints, and owning workload events.',
            'icon': 'circle-x',
            'tone': 'critical',
        }
    if state_label == 'Not Ready':
        return {
            'title': 'Investigate Pod Readiness',
            'description': 'Review container readiness, Pod conditions, probe failures, and runtime reasons before treating the Pod as available.',
            'icon': 'shield-alert',
            'tone': 'warning',
        }
    if state_label == 'Starting':
        return {
            'title': 'Validate Pod Startup',
            'description': 'Confirm scheduling, image pull, initialization, and volume attachment continue progressing.',
            'icon': 'loader-circle',
            'tone': 'warning',
        }
    if state_label == 'Completed':
        return {
            'title': 'Completed Pod Snapshot',
            'description': 'The Pod completed successfully in the committed snapshot. Confirm retention and cleanup follow the owning workload policy.',
            'icon': 'circle-check-big',
            'tone': 'info',
        }
    if restart_count > 0:
        return {
            'title': 'Review Restart Activity',
            'description': 'The committed snapshot reports container restarts. Review current runtime reasons before concluding the issue is active.',
            'icon': 'rotate-ccw',
            'tone': 'warning',
        }
    if not container_statuses:
        return {
            'title': 'Refresh Container Runtime Evidence',
            'description': 'Container runtime evidence was not reported. Refresh inventory before making runtime availability decisions.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    return {
        'title': 'Pod Snapshot Ready for Review',
        'description': 'No exceptional runtime signal is present in the current committed inventory snapshot.',
        'icon': 'circle-check',
        'tone': 'normal',
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
    query = db.session.query(
        PodInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == PodInventory.cluster_id)
    query = filter_current_generation(query, PodInventory)
    query = _apply_pod_filters(
        query,
        cluster_id=cluster_id,
        namespace=namespace,
        status=status,
        owner_type=owner_type,
        node=node,
        search=search,
    )

    summary_rows = (
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
    image_rows = query.with_entities(PodInventory.container_images, PodInventory.init_container_images).all()
    owner_type_count = (
        query.with_entities(func.count(func.distinct(func.coalesce(PodInventory.workload_type, 'Standalone')))).scalar()
        or 0
    )

    pods, pagination = paginate_query(
        query.order_by(Cluster.name, PodInventory.namespace, PodInventory.pod_name),
        page=page,
        per_page=per_page,
    )

    state_counts = {state: 0 for state in _OPERATIONAL_STATE_TONES}
    status_counts: dict[str, int] = {}
    restart_activity = 0
    total_image_references = 0
    for phase, ready, count, restarted_count, image_count in summary_rows:
        state_label, _, _ = _pod_operational_state(phase, ready)
        state_counts[state_label] += int(count or 0)
        phase_label = str(phase or 'Unknown')
        status_counts[phase_label] = status_counts.get(phase_label, 0) + int(count or 0)
        restart_activity += int(restarted_count or 0)
        total_image_references += int(image_count or 0)

    unique_images: set[str] = set()
    for container_images, init_container_images in image_rows:
        unique_images.update(container_images or [])
        unique_images.update(init_container_images or [])

    pod_data = []
    for pod, cluster_name, cluster_environment in pods:
        operational_state, state_tone, state_evidence = _pod_operational_state(pod.phase, pod.ready)
        ready_count, ready_total = _pod_ready_values(pod.ready)
        container_count = _pod_container_count(pod)
        owner_display = (
            f'{pod.workload_type} · {pod.workload_name}'
            if pod.workload_type and pod.workload_name
            else 'Standalone'
        )
        pod_data.append(
            {
                'id': pod.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': pod.namespace,
                'name': pod.pod_name,
                'node': pod.node_name,
                'ready': pod.ready or '0/0',
                'ready_count': ready_count,
                'ready_total': ready_total,
                'restarts': pod.restart_count or 0,
                'ip': pod.pod_ip,
                'status': pod.phase or 'Unknown',
                'operational_state_label': operational_state,
                'operational_state_tone': state_tone,
                'state_evidence': state_evidence,
                'owner_type': pod.workload_type or 'Standalone',
                'owner_name': pod.workload_name or '-',
                'owner_display': owner_display,
                'container_count': container_count,
                'identity_supporting': f"{container_count} Container" + ('s' if container_count != 1 else '') + f' · Age {format_age(pod.created_at)}',
                'placement_primary': pod.node_name or 'Not Scheduled',
                'placement_secondary': pod.pod_ip or 'Pod IP Not Reported',
                'activity_secondary': f"{pod.restart_count or 0} Restart" + ('' if (pod.restart_count or 0) == 1 else 's'),
            }
        )

    total_pods = pagination['total_items']
    overall_posture, overall_tone = _overall_posture(total_pods, state_counts)
    scope_label = 'All Clusters'
    if cluster_id:
        scope_label = next((row.cluster_name for row in pods if str(row[0].cluster_id) == str(cluster_id)), 'Selected Cluster')
        if pod_data:
            scope_label = pod_data[0]['cluster_name']

    return {
        'total_pods': total_pods,
        'ready_count': state_counts['Ready'],
        'exception_count': state_counts['Starting'] + state_counts['Not Ready'] + state_counts['Failed'] + state_counts['Unknown'],
        'starting_count': state_counts['Starting'],
        'not_ready_count': state_counts['Not Ready'],
        'failed_count': state_counts['Failed'],
        'completed_count': state_counts['Completed'],
        'unknown_count': state_counts['Unknown'],
        'restart_activity': restart_activity,
        'unique_image_count': len(unique_images),
        'total_image_references': total_image_references,
        'owner_type_count': owner_type_count,
        'overall_posture': overall_posture,
        'overall_posture_tone': overall_tone,
        'scope_label': scope_label,
        'status_counts': status_counts,
        'pods': pod_data,
        'pagination': pagination,
    }


def get_pod_detail(pod_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        PodInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == PodInventory.cluster_id)
    query = filter_current_generation(query, PodInventory)
    result = query.filter(PodInventory.id == pod_id).first()
    if result is None:
        return None

    pod, cluster_name, cluster_environment = result
    details = pod.details or {}
    configuration = details.get('configuration') or {}
    placement = details.get('placement') or {}
    raw_conditions = details.get('conditions') or []
    raw_container_statuses = details.get('container_statuses') or []
    volumes = details.get('volumes') or []
    owner_chain = list(details.get('owner_chain') or [])

    if not owner_chain:
        if pod.workload_type and pod.workload_name:
            owner_chain.append({'kind': pod.workload_type, 'name': pod.workload_name})
        owner_chain.append({'kind': 'Pod', 'name': pod.pod_name})

    if not raw_container_statuses:
        names = pod.container_names or []
        raw_container_statuses = []
        for index, image in enumerate(pod.container_images or []):
            raw_container_statuses.append(
                {
                    'name': names[index] if index < len(names) else f'container-{index + 1}',
                    'kind': 'Regular',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not Reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                }
            )
        for index, image in enumerate(pod.init_container_images or []):
            raw_container_statuses.append(
                {
                    'name': f'init-container-{index + 1}',
                    'kind': 'Init',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not Reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                }
            )

    container_statuses = [_container_presentation(container) for container in raw_container_statuses]
    conditions = [_condition_presentation(condition) for condition in raw_conditions]
    operational_state, operational_state_tone, state_evidence = _pod_operational_state(pod.phase, pod.ready)
    ready_count, ready_total = _pod_ready_values(pod.ready)
    owner_display = (
        f'{pod.workload_type} · {pod.workload_name}'
        if pod.workload_type and pod.workload_name
        else 'Standalone'
    )
    placement_rows = [
        {'label': 'Node', 'value': pod.node_name or 'Not Scheduled'},
        {'label': 'Pod IP', 'value': pod.pod_ip or 'Not Reported'},
        {'label': 'Host IP', 'value': details.get('host_ip') or 'Not Reported'},
        {'label': 'Scheduler', 'value': placement.get('scheduler') or '-'},
        {'label': 'Priority Class', 'value': placement.get('priority_class') or '-'},
        {'label': 'Topology Spread', 'value': str(int(placement.get('topology_spread_count') or 0))},
    ]
    specification_rows = [
        {'label': 'Service Account', 'value': configuration.get('service_account') or 'default'},
        {'label': 'Restart Policy', 'value': configuration.get('restart_policy') or '-'},
        {'label': 'DNS Policy', 'value': configuration.get('dns_policy') or '-'},
        {'label': 'QoS Class', 'value': details.get('qos_class') or '-'},
        {'label': 'Runtime Class', 'value': configuration.get('runtime_class') or '-'},
        {'label': 'Host Network', 'value': _display_boolean(bool(placement.get('host_network')))},
        {'label': 'Security Context', 'value': 'Reported' if configuration.get('security_context_configured') else 'Not Reported'},
        {'label': 'Image Pull Secrets', 'value': str(int(configuration.get('image_pull_secret_count') or 0))},
        {'label': 'Volumes', 'value': str(int(configuration.get('volume_count') or len(volumes)))},
        {'label': 'Containers', 'value': str(int(configuration.get('container_count') or _pod_container_count(pod)))},
        {'label': 'Init Containers', 'value': str(int(configuration.get('init_container_count') or len(pod.init_container_images or [])))},
        {'label': 'Ephemeral Containers', 'value': str(int(configuration.get('ephemeral_container_count') or 0))},
    ]
    node_selectors = dict(sorted((placement.get('node_selector') or {}).items()))
    tolerations = {
        f'Toleration {index + 1}': str(value)
        for index, value in enumerate(placement.get('tolerations') or [])
    }
    configuration_references = [
        {
            'name': str(reference.get('name') or '-'),
            'supporting_primary': str(reference.get('type') or 'Configuration'),
            'supporting_secondary': 'Referenced by Pod configuration',
            'status': None,
            'status_tone': None,
        }
        for reference in (pod.configuration_references or [])
        if isinstance(reference, dict)
    ]
    storage_references = [
        {
            'name': str(claim_name),
            'supporting_primary': 'PersistentVolumeClaim',
            'supporting_secondary': 'Referenced by Pod volumes',
            'status': None,
            'status_tone': None,
        }
        for claim_name in (pod.persistent_volume_claims or [])
    ]

    return {
        'id': pod.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': pod.namespace,
        'name': pod.pod_name,
        'node': pod.node_name,
        'ready': pod.ready or '0/0',
        'ready_count': ready_count,
        'ready_total': ready_total,
        'restarts': pod.restart_count or 0,
        'ip': pod.pod_ip,
        'host_ip': details.get('host_ip'),
        'status': pod.phase or 'Unknown',
        'operational_state_label': operational_state,
        'operational_state_tone': operational_state_tone,
        'state_evidence': state_evidence,
        'reason': details.get('reason'),
        'message': details.get('message'),
        'qos_class': details.get('qos_class') or '-',
        'owner_type': pod.workload_type or 'Standalone',
        'owner_name': pod.workload_name or '-',
        'owner_display': owner_display,
        'owner_chain': owner_chain,
        'uid': details.get('uid') or '-',
        'conditions': conditions,
        'condition_evidence_rows': [
            {
                'label': condition['type'],
                'value': condition['state_label'],
                'supporting': condition.get('reason') or 'No reason reported',
            }
            for condition in conditions
        ],
        'placement': {
            'scheduler': placement.get('scheduler') or '-',
            'priority_class': placement.get('priority_class') or '-',
            'node_selector': node_selectors,
            'tolerations': placement.get('tolerations') or [],
            'affinity_configured': bool(placement.get('affinity_configured')),
            'topology_spread_count': int(placement.get('topology_spread_count') or 0),
            'host_network': bool(placement.get('host_network')),
        },
        'placement_rows': placement_rows,
        'placement_constraint_count': len(node_selectors)
        + len(placement.get('tolerations') or [])
        + int(bool(placement.get('affinity_configured')))
        + int(placement.get('topology_spread_count') or 0),
        'placement_evidence_rows': [
            {'label': 'Node Selector', 'value': f'{len(node_selectors)} rule' + ('s' if len(node_selectors) != 1 else '')},
            {'label': 'Affinity', 'value': 'Configured' if placement.get('affinity_configured') else 'Not Configured'},
            {'label': 'Tolerations', 'value': str(len(placement.get('tolerations') or []))},
            {'label': 'Topology Spread', 'value': str(int(placement.get('topology_spread_count') or 0))},
        ],
        'configuration': {
            'service_account': configuration.get('service_account') or 'default',
            'restart_policy': configuration.get('restart_policy') or '-',
            'dns_policy': configuration.get('dns_policy') or '-',
            'runtime_class': configuration.get('runtime_class') or '-',
            'security_context_configured': bool(configuration.get('security_context_configured')),
            'image_pull_secret_count': int(configuration.get('image_pull_secret_count') or 0),
            'volume_count': int(configuration.get('volume_count') or len(volumes)),
            'container_count': int(configuration.get('container_count') or _pod_container_count(pod)),
            'init_container_count': int(configuration.get('init_container_count') or len(pod.init_container_images or [])),
            'ephemeral_container_count': int(configuration.get('ephemeral_container_count') or 0),
        },
        'specification_rows': specification_rows,
        'node_selectors': node_selectors,
        'toleration_entries': tolerations,
        'container_statuses': container_statuses,
        'volumes': volumes,
        'configuration_references': configuration_references,
        'storage_references': storage_references,
        'labels': dict(sorted((pod.labels or {}).items())),
        'annotations': dict(sorted((details.get('annotations') or {}).items())),
        'age': format_age(pod.created_at),
        'created_at': pod.created_at,
        'collected_at': pod.collected_at,
        'operational_context': _operational_context(
            operational_state,
            pod.restart_count or 0,
            container_statuses,
        ),
    }
