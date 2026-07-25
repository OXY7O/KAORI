from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.formatting import convert_ki_to_gib, convert_storage_to_gib, format_kubernetes_size
from app.inventory.resources.common import format_age
from app.inventory.resources.descriptions import NODE_ROLE_DESCRIPTIONS
from app.models import Cluster, NodeInventory, PodInventory


def get_node_filter_roles(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NodeInventory.role,
    )
    query = filter_current_generation(query, NodeInventory)

    if cluster_id:
        query = query.filter(
            NodeInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NodeInventory.role,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_node_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NodeInventory.status,
    )
    query = filter_current_generation(query, NodeInventory)

    if cluster_id:
        query = query.filter(
            NodeInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NodeInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_node_inventory(
    cluster_id=None,
    role=None,
    status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = db.session.query(
        NodeInventory,
        Cluster.name.label(
            'cluster_name',
        ),
        Cluster.environment.label(
            'cluster_environment',
        ),
    ).join(
        Cluster,
        Cluster.id == NodeInventory.cluster_id,
    )
    query = filter_current_generation(query, NodeInventory)

    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)

    if role:
        query = query.filter(NodeInventory.role == role)

    if status:
        query = query.filter(NodeInventory.status == status)

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                NodeInventory.node_name.ilike(
                    search_pattern,
                ),
                NodeInventory.internal_ip.ilike(
                    search_pattern,
                ),
                NodeInventory.external_ip.ilike(
                    search_pattern,
                ),
                NodeInventory.hostname_address.ilike(
                    search_pattern,
                ),
            )
        )

    summary_rows = query.with_entities(
        NodeInventory.cpu,
        NodeInventory.memory,
        NodeInventory.ephemeral_storage,
        NodeInventory.status,
    ).all()
    nodes, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            NodeInventory.node_name,
        ),
        page=page,
        per_page=per_page,
    )

    nodes_data = []

    for node, cluster_name, cluster_environment in nodes:
        runtime = node.container_runtime or ''

        runtime_display = runtime.split('://')[0] if '://' in runtime else runtime

        node_status = node.status or 'Unknown'

        nodes_data.append(
            {
                'id': node.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'node_name': node.node_name,
                'role': node.role,
                'status': node_status,
                'status_display': 'Not Ready' if node_status == 'NotReady' else node_status,
                'internal_ip': node.internal_ip,
                'external_ip': node.external_ip,
                'hostname_address': node.hostname_address,
                'has_extra_addresses': bool(
                    node.external_ip or node.hostname_address,
                ),
                'cpu': node.cpu,
                'memory_display': format_kubernetes_size(
                    node.memory,
                ),
                'ephemeral_storage_display': format_kubernetes_size(
                    node.ephemeral_storage,
                ),
                'ephemeral_storage_allocatable_display': format_kubernetes_size(
                    node.ephemeral_storage_allocatable,
                ),
                'os_image': node.os_image,
                'runtime_display': runtime_display,
                'collected_at': node.collected_at,
            }
        )

    total_cpu = sum(cpu or 0 for cpu, _, _, _ in summary_rows)
    total_memory = round(sum(convert_ki_to_gib(memory) for _, memory, _, _ in summary_rows), 1)
    total_ephemeral_storage = round(
        sum(convert_storage_to_gib(storage) for _, _, storage, _ in summary_rows),
        1,
    )
    ready_nodes = sum(1 for _, _, _, node_status in summary_rows if node_status == 'Ready')
    not_ready_nodes = sum(1 for _, _, _, node_status in summary_rows if node_status == 'NotReady')

    return {
        'total_nodes': pagination['total_items'],
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
        'total_cpu': total_cpu,
        'total_memory': total_memory,
        'total_ephemeral_storage': total_ephemeral_storage,
        'nodes': nodes_data,
        'pagination': pagination,
    }


def get_node_detail(node_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        NodeInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == NodeInventory.cluster_id)
    query = filter_current_generation(query, NodeInventory)
    result = query.filter(NodeInventory.id == node_id).first()

    if result is None:
        return None

    node, cluster_name = result
    runtime = node.container_runtime or ''
    role = node.role or 'Unknown'
    role_key = role.lower()

    pod_scope = (
        PodInventory.cluster_id == node.cluster_id,
        PodInventory.node_name == node.node_name,
    )
    pod_count_query = db.session.query(func.count(PodInventory.id))
    pod_count_query = filter_current_generation(pod_count_query, PodInventory)
    scheduled_pod_count = pod_count_query.filter(*pod_scope).scalar() or 0

    if node.unschedulable is True:
        scheduling_display = 'Cordoned'
    elif node.unschedulable is False:
        scheduling_display = 'Schedulable'
    else:
        scheduling_display = 'Not reported'

    network_availability = 'Not reported'
    if node.network_unavailable == 'True':
        network_availability = 'Unavailable'
    elif node.network_unavailable == 'False':
        network_availability = 'Available'

    ready_condition = {
        'Ready': 'Ready',
        'NotReady': 'Not Ready',
    }.get(node.status or '', 'Unknown')

    def pressure_display(value: str | None) -> str:
        if value == 'True':
            return 'Pressure Detected'
        if value == 'False':
            return 'Normal'
        return 'Not Reported'

    node_labels = node.labels or {}
    operating_system = node.operating_system or node_labels.get('kubernetes.io/os') or 'Unknown'
    operating_system_display = (
        operating_system.title() if operating_system.lower() in {'linux', 'windows'} else operating_system
    )
    architecture = node.architecture or node_labels.get('kubernetes.io/arch') or 'Not reported'

    return {
        'id': node.id,
        'cluster_name': cluster_name,
        'node_name': node.node_name,
        'system_uuid': node.system_uuid or 'Not reported',
        'role': role,
        'age': format_age(node.created_at),
        'role_description': NODE_ROLE_DESCRIPTIONS.get(
            role_key,
            'Provides Kubernetes node capacity. Its exact function depends on the labels and workloads assigned to it.',
        ),
        'status': node.status or 'Unknown',
        'status_display': 'Not Ready' if node.status == 'NotReady' else (node.status or 'Unknown'),
        'internal_ip': node.internal_ip,
        'external_ip': node.external_ip,
        'hostname_address': node.hostname_address,
        'scheduled_pod_count': scheduled_pod_count,
        'network_availability': network_availability,
        'scheduling_display': scheduling_display,
        'ready_condition': ready_condition,
        'memory_pressure': pressure_display(node.memory_pressure),
        'disk_pressure': pressure_display(node.disk_pressure),
        'pid_pressure': pressure_display(node.pid_pressure),
        'taints': node.taints or [],
        'labels': dict(
            sorted(
                node_labels.items(),
            )
        ),
        'operating_system_display': operating_system_display,
        'architecture': architecture,
        'kubelet_version': node.kubelet_version or 'Not reported',
        'kube_proxy_version': node.kube_proxy_version or 'Not reported',
        'cpu': node.cpu,
        'memory_display': format_kubernetes_size(node.memory),
        'ephemeral_storage_display': format_kubernetes_size(node.ephemeral_storage),
        'ephemeral_storage_allocatable_display': format_kubernetes_size(node.ephemeral_storage_allocatable),
        'os_image': node.os_image,
        'kernel_version': node.kernel_version,
        'runtime_display': runtime.split('://')[0] if '://' in runtime else runtime,
        'collected_at': node.collected_at,
    }
