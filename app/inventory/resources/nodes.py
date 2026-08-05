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


def _reported_false(value: object) -> bool:
    return value is False or str(value or '').strip().lower() == 'false'


def _role_display(role: str | None) -> str:
    role_value = role or 'Unknown'
    if role_value.lower() in {'control-plane', 'master'}:
        return 'Control Plane'
    return role_value.replace('_', ' ').replace('-', ' ').title()


def _status_display(status: str | None) -> str:
    return {'Ready': 'Ready', 'NotReady': 'Not Ready'}.get(status or '', status or 'Unknown')


def _status_tone(status: str | None) -> str:
    return 'normal' if status == 'Ready' else ('critical' if status == 'NotReady' else 'unknown')


def _node_filter_values(column: Any, cluster_id: str | None = None) -> list[str]:
    query = db.session.query(column)
    query = filter_current_generation(query, NodeInventory)
    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(column).all()
    return [row[0] for row in rows if row[0]]


def get_node_filter_roles(cluster_id: str | None = None) -> list[dict[str, str]]:
    values = _node_filter_values(NodeInventory.role, cluster_id)
    return [
        {'value': value, 'label': _role_display(value)}
        for value in sorted(values, key=lambda item: _role_display(item).lower())
    ]


def get_node_filter_statuses(cluster_id: str | None = None) -> list[dict[str, str]]:
    values = _node_filter_values(NodeInventory.status, cluster_id)
    return [
        {'value': value, 'label': _status_display(value)}
        for value in sorted(values, key=lambda item: _status_display(item).lower())
    ]


def _coverage_tone(reported: int, total: int) -> str:
    if total == 0 or reported == 0:
        return 'unknown'
    return 'normal' if reported == total else 'warning'


def _coverage_description(reported: int, total: int) -> str:
    if total == 0:
        return 'No nodes match the current filters.'
    if reported == total:
        return f'Reported by all {total} filtered node{"s" if total != 1 else ""}.'
    return f'Reported by {reported} of {total} filtered nodes.'


def _node_condition_labels(node: NodeInventory) -> list[str]:
    labels: list[str] = []
    if _reported_true(node.unschedulable):
        labels.append('Cordoned')
    if _reported_true(node.memory_pressure):
        labels.append('Memory Pressure')
    if _reported_true(node.disk_pressure):
        labels.append('Disk Pressure')
    if _reported_true(node.pid_pressure):
        labels.append('PID Pressure')
    if _reported_true(node.network_unavailable):
        labels.append('Network Unavailable')
    return labels


def _node_condition_summary(labels: list[str], status: str | None) -> str:
    if not labels and status not in {'Ready', 'NotReady'}:
        return 'Readiness evidence incomplete'
    if not labels:
        return 'No active conditions'
    if len(labels) <= 2:
        return ' · '.join(labels)
    return f'{labels[0]} · {labels[1]} · +{len(labels) - 2} more'


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
        condition_labels = _node_condition_labels(node)
        scheduling_display = (
            'Cordoned'
            if _reported_true(node.unschedulable)
            else ('Schedulable' if _reported_false(node.unschedulable) else 'Scheduling Not Reported')
        )
        network_scope = (
            'External Address Available'
            if node.external_ip
            else ('Private Node' if node.internal_ip else 'Address Not Reported')
        )
        nodes_data.append(
            {
                'id': node.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'node_name': node.node_name,
                'role_display': _role_display(node.role),
                'status_display': _status_display(node_status),
                'status_tone': _status_tone(node_status),
                'scheduling_display': scheduling_display,
                'condition_summary': _node_condition_summary(condition_labels, node_status),
                'condition_count': len(condition_labels),
                'internal_ip': node.internal_ip,
                'network_scope': network_scope,
                'capacity_primary': f"{node.cpu if node.cpu is not None else '-'} CPU · {memory_display}",
                'capacity_secondary': (
                    f'{ephemeral_display} Ephemeral'
                    if ephemeral_display != '-'
                    else 'Ephemeral storage not reported'
                ),
                'identity_supporting': ' · '.join(
                    value for value in (node.os_image, runtime_display) if value
                )
                or 'Platform details not reported',
            }
        )

    total_nodes = pagination['total_items']
    cpu_reported_nodes = sum(1 for row in summary_rows if row[0] is not None)
    memory_reported_nodes = sum(1 for row in summary_rows if format_kubernetes_size(row[1]) != '-')
    ephemeral_reported_nodes = sum(1 for row in summary_rows if format_kubernetes_size(row[2]) != '-')

    total_cpu = sum(row[0] for row in summary_rows if row[0] is not None)
    total_memory = round(
        sum(convert_ki_to_gib(row[1]) for row in summary_rows if format_kubernetes_size(row[1]) != '-'),
        1,
    )
    total_ephemeral_storage = round(
        sum(
            convert_storage_to_gib(row[2])
            for row in summary_rows
            if format_kubernetes_size(row[2]) != '-'
        ),
        1,
    )
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

    if total_nodes == 0:
        fleet_posture_tone, fleet_posture_label = 'unknown', 'No Data'
    elif not_ready_nodes == total_nodes:
        fleet_posture_tone, fleet_posture_label = 'critical', 'Critical'
    elif not_ready_nodes > 0 or network_issue_nodes > 0:
        fleet_posture_tone, fleet_posture_label = 'warning', 'Attention'
    elif pressure_nodes > 0 or cordoned_nodes > 0:
        fleet_posture_tone, fleet_posture_label = 'warning', 'Attention'
    elif unknown_nodes > 0:
        fleet_posture_tone, fleet_posture_label = 'unknown', 'Incomplete'
    else:
        fleet_posture_tone, fleet_posture_label = 'normal', 'Healthy'

    return {
        'total_nodes': total_nodes,
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
        'unknown_nodes': unknown_nodes,
        'cordoned_nodes': cordoned_nodes,
        'pressure_nodes': pressure_nodes,
        'network_issue_nodes': network_issue_nodes,
        'active_signal_nodes': active_signal_nodes,
        'fleet_posture_tone': fleet_posture_tone,
        'fleet_posture_label': fleet_posture_label,
        'total_cpu_display': f'{total_cpu} Cores' if cpu_reported_nodes else 'Not Available',
        'cpu_coverage_tone': _coverage_tone(cpu_reported_nodes, total_nodes),
        'cpu_coverage_description': _coverage_description(cpu_reported_nodes, total_nodes),
        'total_memory_display': f'{total_memory:g} GiB' if memory_reported_nodes else 'Not Available',
        'memory_coverage_tone': _coverage_tone(memory_reported_nodes, total_nodes),
        'memory_coverage_description': _coverage_description(memory_reported_nodes, total_nodes),
        'total_ephemeral_storage_display': (
            f'{total_ephemeral_storage:g} GiB' if ephemeral_reported_nodes else 'Not Available'
        ),
        'ephemeral_coverage_tone': _coverage_tone(ephemeral_reported_nodes, total_nodes),
        'ephemeral_coverage_description': _coverage_description(ephemeral_reported_nodes, total_nodes),
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

    if _reported_true(node.unschedulable):
        scheduling_display = 'Cordoned'
    elif _reported_false(node.unschedulable):
        scheduling_display = 'Schedulable'
    else:
        scheduling_display = 'Not Reported'

    network_availability = 'Not Reported'
    if _reported_true(node.network_unavailable):
        network_availability = 'Unavailable'
    elif _reported_false(node.network_unavailable):
        network_availability = 'Available'

    ready_condition = {'Ready': 'Ready', 'NotReady': 'Not Ready'}.get(node.status or '', 'Unknown')

    def pressure_display(value: str | None) -> str:
        if _reported_true(value):
            return 'Pressure Detected'
        if _reported_false(value):
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
    elif ready_condition == 'Unknown':
        operational_context = {
            'title': 'Validate Node Readiness Evidence',
            'description': (
                'Readiness is not reported in the committed snapshot. Confirm kubelet state '
                'and collection coverage before relying on this node for placement decisions.'
            ),
            'tone': 'unknown',
            'icon': 'circle-help',
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
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'node_name': node.node_name,
        'system_uuid': node.system_uuid or 'Not Reported',
        'role_display': _role_display(role),
        'age': format_age(node.created_at),
        'role_description': NODE_ROLE_DESCRIPTIONS.get(
            role_key,
            'Provides Kubernetes node capacity. Its exact function depends on the labels and workloads assigned to it.',
        ),
        'status': node.status or 'Unknown',
        'status_display': _status_display(node.status),
        'internal_ip': node.internal_ip,
        'external_ip': node.external_ip,
        'hostname_address': node.hostname_address,
        'scheduled_pod_count': scheduled_pod_count,
        'network_availability': network_availability,
        'network_scope': (
            'External Address Available'
            if node.external_ip
            else ('Private Node' if node.internal_ip else 'Address Not Reported')
        ),
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
        'container_runtime_identifier': runtime or 'Not Reported',
        'collected_at': node.collected_at,
        'operational_context': operational_context,
    }
