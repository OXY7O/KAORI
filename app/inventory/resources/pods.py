from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_

from app.common.inventory_generation import filter_current_generation
from app.extensions import db
from app.inventory.resources.common import format_age
from app.models import Cluster, PodInventory


def get_pod_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.namespace,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.namespace,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_pod_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.phase,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.phase,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_pod_filter_owner_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.workload_type,
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.workload_type,
        )
        .all()
    )

    owner_types = [row[0] for row in rows if row[0]]
    standalone_exists = db.session.query(PodInventory.id).filter(
        PodInventory.workload_type.is_(None),
    )
    if cluster_id:
        standalone_exists = standalone_exists.filter(
            PodInventory.cluster_id == cluster_id,
        )
    if namespace:
        standalone_exists = standalone_exists.filter(
            PodInventory.namespace == namespace,
        )
    if standalone_exists.first() is not None:
        owner_types.append('Standalone')

    return sorted(set(owner_types))


def get_pod_filter_nodes(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        PodInventory.node_name,
    ).filter(
        PodInventory.node_name.is_not(None),
        PodInventory.node_name != '',
    )

    if cluster_id:
        query = query.filter(
            PodInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            PodInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            PodInventory.node_name,
        )
        .all()
    )

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

    ready_value = pod.ready or ''
    if '/' in ready_value:
        try:
            return int(ready_value.split('/', maxsplit=1)[1])
        except (TypeError, ValueError):
            pass

    return 0


def _pod_ready_values(value: str | None) -> tuple[int, int]:
    if not value or '/' not in value:
        return 0, 0

    ready, total = value.split('/', maxsplit=1)
    try:
        return int(ready), int(total)
    except (TypeError, ValueError):
        return 0, 0


def _parse_inventory_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def get_pod_inventory(
    cluster_id=None,
    namespace=None,
    status=None,
    owner_type=None,
    node=None,
    search=None,
):
    query = db.session.query(
        PodInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == PodInventory.cluster_id,
    )
    query = filter_current_generation(query, PodInventory)

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

    pods = query.order_by(
        Cluster.name,
        PodInventory.namespace,
        PodInventory.pod_name,
    ).all()

    status_counts: dict[str, int] = {}
    pod_data = []

    running = 0
    pending = 0
    failed = 0

    for pod, cluster_name in pods:
        phase = pod.phase or 'Unknown'
        status_counts[phase] = status_counts.get(phase, 0) + 1

        if phase == 'Running':
            running += 1
        elif phase == 'Pending':
            pending += 1
        elif phase == 'Failed':
            failed += 1

        container_images = pod.container_images or []
        init_container_images = pod.init_container_images or []
        all_images = container_images + init_container_images
        image_count = pod.image_count or len(all_images)
        ready_count, total_count = _pod_ready_values(pod.ready)
        container_count = _pod_container_count(pod)

        pod_data.append(
            {
                'id': pod.id,
                'cluster_name': cluster_name,
                'namespace': pod.namespace,
                'name': pod.pod_name,
                'node': pod.node_name,
                'ready': pod.ready or '0/0',
                'ready_count': ready_count,
                'ready_total': total_count,
                'restarts': pod.restart_count or 0,
                'ip': pod.pod_ip,
                'status': phase,
                'owner_type': pod.workload_type or 'Standalone',
                'owner_name': pod.workload_name or '-',
                'container_count': container_count,
                'container_images': container_images,
                'init_container_images': init_container_images,
                'all_images': all_images,
                'image_count': image_count,
            }
        )

    return {
        'total_pods': len(pods),
        'running': running,
        'pending': pending,
        'failed': failed,
        'total_image_references': sum(pod.get('image_count', 0) for pod in pod_data),
        'unique_image_count': len({image for pod in pod_data for image in pod.get('all_images', [])}),
        'status_counts': status_counts,
        'pod_statuses': get_pod_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'owner_types': get_pod_filter_owner_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'nodes': get_pod_filter_nodes(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'namespaces': get_pod_filter_namespaces(cluster_id),
        'pods': pod_data,
    }


def get_pod_detail(
    pod_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            PodInventory,
            Cluster.name.label(
                'cluster_name',
            ),
        )
        .join(
            Cluster,
            Cluster.id == PodInventory.cluster_id,
        )
        .filter(
            PodInventory.id == pod_id,
        )
        .first()
    )

    if result is None:
        return None

    pod, cluster_name = result
    details = pod.details or {}
    configuration = details.get('configuration') or {}
    placement = details.get('placement') or {}
    conditions = details.get('conditions') or []
    container_statuses = details.get('container_statuses') or []
    volumes = details.get('volumes') or []
    owner_chain = details.get('owner_chain') or []

    if not owner_chain:
        if pod.workload_type and pod.workload_name:
            owner_chain.append(
                {
                    'kind': pod.workload_type,
                    'name': pod.workload_name,
                }
            )
        owner_chain.append({'kind': 'Pod', 'name': pod.pod_name})

    if not container_statuses:
        container_statuses = []
        names = pod.container_names or []
        images = pod.container_images or []
        for index, image in enumerate(images):
            container_statuses.append(
                {
                    'name': names[index] if index < len(names) else f'container-{index + 1}',
                    'kind': 'Regular',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                    'previous_state': 'Unknown',
                    'previous_reason': None,
                }
            )

        for index, image in enumerate(pod.init_container_images or []):
            container_statuses.append(
                {
                    'name': f'init-container-{index + 1}',
                    'kind': 'Init',
                    'image': image,
                    'image_id': '-',
                    'pull_policy': '-',
                    'ready': False,
                    'started': False,
                    'restart_count': 0,
                    'state': 'Not reported',
                    'reason': None,
                    'message': None,
                    'started_at': None,
                    'finished_at': None,
                    'exit_code': None,
                    'previous_state': 'Unknown',
                    'previous_reason': None,
                }
            )

    for container in container_statuses:
        container['started_at_value'] = _parse_inventory_datetime(
            container.get('started_at'),
        )
        container['finished_at_value'] = _parse_inventory_datetime(
            container.get('finished_at'),
        )

    labels = dict(sorted((pod.labels or {}).items()))
    annotations = dict(sorted((details.get('annotations') or {}).items()))
    ready_count, ready_total = _pod_ready_values(pod.ready)

    return {
        'id': pod.id,
        'cluster_name': cluster_name,
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
        'reason': details.get('reason'),
        'message': details.get('message'),
        'qos_class': details.get('qos_class') or '-',
        'owner_type': pod.workload_type or 'Standalone',
        'owner_name': pod.workload_name or '-',
        'owner_chain': owner_chain,
        'uid': details.get('uid') or '-',
        'conditions': conditions,
        'placement': {
            'scheduler': placement.get('scheduler') or '-',
            'priority_class': placement.get('priority_class') or '-',
            'node_selector': placement.get('node_selector') or {},
            'tolerations': placement.get('tolerations') or [],
            'affinity_configured': bool(placement.get('affinity_configured')),
            'topology_spread_count': int(placement.get('topology_spread_count') or 0),
            'host_network': bool(placement.get('host_network')),
        },
        'configuration': {
            'service_account': configuration.get('service_account') or 'default',
            'restart_policy': configuration.get('restart_policy') or '-',
            'dns_policy': configuration.get('dns_policy') or '-',
            'runtime_class': configuration.get('runtime_class') or '-',
            'security_context_configured': bool(configuration.get('security_context_configured')),
            'image_pull_secret_count': int(configuration.get('image_pull_secret_count') or 0),
            'volume_count': int(configuration.get('volume_count') or len(volumes)),
            'container_count': int(configuration.get('container_count') or _pod_container_count(pod)),
            'init_container_count': int(
                configuration.get('init_container_count') or len(pod.init_container_images or [])
            ),
            'ephemeral_container_count': int(configuration.get('ephemeral_container_count') or 0),
        },
        'container_statuses': container_statuses,
        'volumes': volumes,
        'labels': labels,
        'annotations': annotations,
        'age': format_age(pod.created_at),
        'created_at': pod.created_at,
        'collected_at': pod.collected_at,
    }
