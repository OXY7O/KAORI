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


def _reported_true(value: object) -> bool:
    return value is True or str(value or '').strip().lower() == 'true'


def _role_display(role: str | None) -> str:
    role_value = role or 'Unknown'
    if role_value.lower() in {'control-plane', 'master'}:
        return 'Control Plane'
    return role_value.replace('_', ' ').replace('-', ' ').title()


def get_node_filter_roles(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(NodeInventory.role)
    query = filter_current_generation(query, NodeInventory)
    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(NodeInventory.role).all()
    return [row[0] for row in rows if row[0]]


def get_node_filter_statuses(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(NodeInventory.status)
    query = filter_current_generation(query, NodeInventory)
    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(NodeInventory.status).all()
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
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NodeInventory.cluster_id)
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
                NodeInventory.node_name.ilike(search_pattern),
                NodeInventory.internal_ip.ilike(search_pattern),
                NodeInventory.external_ip.ilike(search_pattern),
                NodeInventory.hostname_address.ilike(search_pattern),
            )
        )

    summary_rows = query.with_entities(
        NodeInventory.cpu,
        NodeInventory.memory,
        NodeInventory.ephemeral_storage,
        NodeInventory.status,
        NodeInventory.unschedulable,
        NodeInventory.memory_pressure,
        NodeInventory.disk_pressure,
        NodeInventory.pid_pressure,
        NodeInventory.network_unavailable,
    ).all()
    nodes, pagination = paginate_query(
        query.order_by(Cluster.name, NodeInventory.node_name),
        page=page,
        per_page=per_page,
    )

    nodes_data = []
    for node, cluster_name, cluster_environment in nodes:
        runtime = node.container_runtime or ''
        runtime_display = runtime.split('://')[0] if '://' in runtime else runtime
        node_status = node.status or 'Unknown'
        memory_display = format_kubernetes_size(node.memory)
        ephemeral_display = format_kubernetes_size(node.ephemeral_storage)
        nodes_data.append(
            {
                'id': node.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'node_name': node.node_name,
                'role': node.role,
                'role_display': _role_display(node.role),
                'status': node_status,
                'status_display': 'Not Ready' if node_status == 'NotReady' else node_status,
                'status_tone': (
                    'normal' if node_status == 'Ready' else ('critical' if node_status == 'NotReady' else 'unknown')
                ),
                'internal_ip': node.internal_ip,
                'external_ip': node.external_ip,
                'hostname_address': node.hostname_address,
                'network_scope': 'External Address' if node.external_ip else 'Private Node',
                'cpu': node.cpu,
                'memory_display': memory_display,
                'ephemeral_storage_display': ephemeral_display,
                'ephemeral_storage_allocatable_display': format_kubernetes_size(
                    node.ephemeral_storage_allocatable
                ),
                'capacity_primary': f"{node.cpu or '-'} CPU · {memory_display}",
                'capacity_secondary': f'{ephemeral_display} Ephemeral',
                'os_image': node.os_image,
                'runtime_display': runtime_display or 'Runtime Not Reported',
                'identity_supporting': ' · '.join(
                    value for value in (node.os_image, runtime_display) if value
                )
                or 'Platform details not reported',
                'collected_at': node.collected_at,
            }
        )

    total_cpu = sum(cpu or 0 for cpu, *_ in summary_rows)
    total_memory = round(sum(convert_ki_to_gib(row[1]) for row in summary_rows), 1)
    total_ephemeral_storage = round(sum(convert_storage_to_gib(row[2]) for row in summary_rows), 1)
    ready_nodes = sum(1 for row in summary_rows if row[3] == 'Ready')
    not_ready_nodes = sum(1 for row in summary_rows if row[3] == 'NotReady')
    unknown_nodes = sum(1 for row in summary_rows if row[3] not in {'Ready', 'NotReady'})
    cordoned_nodes = sum(1 for row in summary_rows if _reported_true(row[4]))
    pressure_nodes = sum(1 for row in summary_rows if any(_reported_true(value) for value in row[5:8]))
    network_issue_nodes = sum(1 for row in summary_rows if _reported_true(row[8]))
    active_signal_nodes = sum(
        1
        for row in summary_rows
        if row[3] == 'NotReady'
        or _reported_true(row[4])
        or any(_reported_true(value) for value in row[5:8])
        or _reported_true(row[8])
    )

    total_nodes = pagination['total_items']
    if total_nodes == 0:
        readiness_tone, readiness_label = 'unknown', 'No Data'
    elif not_ready_nodes == total_nodes:
        readiness_tone, readiness_label = 'critical', 'Critical'
    elif not_ready_nodes > 0:
        readiness_tone, readiness_label = 'warning', 'Attention'
    elif unknown_nodes > 0:
        readiness_tone, readiness_label = 'unknown', 'Unknown'
    else:
        readiness_tone, readiness_label = 'normal', 'Healthy'

    return {
        'total_nodes': total_nodes,
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
        'unknown_nodes': unknown_nodes,
        'cordoned_nodes': cordoned_nodes,
        'pressure_nodes': pressure_nodes,
        'network_issue_nodes': network_issue_nodes,
        'active_signal_nodes': active_signal_nodes,
        'readiness_tone': readiness_tone,
        'readiness_label': readiness_label,
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
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NodeInventory.cluster_id)
    query = filter_current_generation(query, NodeInventory)
    result = query.filter(NodeInventory.id == node_id).first()
    if result is None:
        return None

    node, cluster_name, cluster_environment = result
    runtime = node.container_runtime or ''
    role = node.role or 'Unknown'
    role_key = role.lower()

    pod_count_query = db.session.query(func.count(PodInventory.id))
    pod_count_query = filter_current_generation(pod_count_query, PodInventory)
    scheduled_pod_count = (
        pod_count_query.filter(
            PodInventory.cluster_id == node.cluster_id,
            PodInventory.node_name == node.node_name,
        ).scalar()
        or 0
    )

    if node.unschedulable is True:
        scheduling_display = 'Cordoned'
    elif node.unschedulable is False:
        scheduling_display = 'Schedulable'
    else:
        scheduling_display = 'Not Reported'

    network_availability = 'Not Reported'
    if _reported_true(node.network_unavailable):
        network_availability = 'Unavailable'
    elif str(node.network_unavailable or '').lower() == 'false':
        network_availability = 'Available'

    ready_condition = {'Ready': 'Ready', 'NotReady': 'Not Ready'}.get(node.status or '', 'Unknown')

    def pressure_display(value: str | None) -> str:
        if _reported_true(value):
            return 'Pressure Detected'
        if str(value or '').lower() == 'false':
            return 'Normal'
        return 'Not Reported'

    memory_pressure = pressure_display(node.memory_pressure)
    disk_pressure = pressure_display(node.disk_pressure)
    pid_pressure = pressure_display(node.pid_pressure)
    has_pressure = 'Pressure Detected' in {memory_pressure, disk_pressure, pid_pressure}

    if ready_condition == 'Not Ready':
        operational_context = {
            'title': 'Investigate Node Readiness',
            'description': (
                'Review kubelet health, network availability, pressure conditions, '
                'and recent cluster events before rescheduling workloads.'
            ),
            'tone': 'critical',
            'icon': 'shield-alert',
        }
    elif network_availability == 'Unavailable':
        operational_context = {
            'title': 'Restore Node Network Availability',
            'description': (
                'Confirm the node network path and CNI condition before relying on '
                'this node for workload placement.'
            ),
            'tone': 'critical',
            'icon': 'network-x',
        }
    elif has_pressure:
        operational_context = {
            'title': 'Resolve Resource Pressure',
            'description': (
                'Review workload placement and resource consumption before the '
                'condition affects additional Pods.'
            ),
            'tone': 'warning',
            'icon': 'gauge',
        }
    elif scheduling_display == 'Cordoned':
        operational_context = {
            'title': 'Review Scheduling Boundary',
            'description': (
                'The node is cordoned. Confirm whether this is planned maintenance '
                'before making it schedulable again.'
            ),
            'tone': 'warning',
            'icon': 'circle-pause',
        }
    else:
        operational_context = {
            'title': 'Node Ready for Scheduling',
            'description': (
                'No critical readiness, network, or pressure signal is present in '
                'the current committed inventory snapshot.'
            ),
            'tone': 'normal',
            'icon': 'circle-check',
        }

    node_labels = node.labels or {}
    operating_system = node.operating_system or node_labels.get('kubernetes.io/os') or 'Unknown'
    operating_system_display = (
        operating_system.title() if operating_system.lower() in {'linux', 'windows'} else operating_system
    )
    architecture = node.architecture or node_labels.get('kubernetes.io/arch') or 'Not Reported'

    return {
        'id': node.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'node_name': node.node_name,
        'system_uuid': node.system_uuid or 'Not Reported',
        'role': role,
        'role_display': _role_display(role),
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
        'memory_pressure': memory_pressure,
        'disk_pressure': disk_pressure,
        'pid_pressure': pid_pressure,
        'has_pressure': has_pressure,
        'taints': node.taints or [],
        'labels': dict(sorted(node_labels.items())),
        'operating_system_display': operating_system_display,
        'architecture': architecture,
        'kubelet_version': node.kubelet_version or 'Not Reported',
        'kube_proxy_version': node.kube_proxy_version or 'Not Reported',
        'cpu': node.cpu,
        'memory_display': format_kubernetes_size(node.memory),
        'ephemeral_storage_display': format_kubernetes_size(node.ephemeral_storage),
        'ephemeral_storage_allocatable_display': format_kubernetes_size(node.ephemeral_storage_allocatable),
        'os_image': node.os_image or 'Not Reported',
        'kernel_version': node.kernel_version or 'Not Reported',
        'runtime_display': runtime.split('://')[0] if '://' in runtime else (runtime or 'Not Reported'),
        'container_runtime_identifier': runtime or 'Not Reported',
        'collected_at': node.collected_at,
        'operational_context': operational_context,
    }
