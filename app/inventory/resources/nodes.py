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


def _canonical_role_filter(role: str | None) -> str:
    role_value = str(role or '').strip()
    if role_value.lower() in {'control-plane', 'master'}:
        return 'control-plane'
    return role_value


def _status_display(status: str | None) -> str:
    return {'Ready': 'Ready', 'NotReady': 'Not Ready'}.get(status or '', status or 'Unknown')


def _status_tone(status: str | None) -> str:
    return 'normal' if status == 'Ready' else ('critical' if status == 'NotReady' else 'unknown')


def _node_filter_values(column: Any, cluster_id: str | None = None) -> list[str]:
    query = filter_current_generation(db.session.query(column), NodeInventory)
    if cluster_id:
        query = query.filter(NodeInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(column).all()
    return [row[0] for row in rows if row[0]]


def get_node_filter_roles(cluster_id: str | None = None) -> list[dict[str, str]]:
    values = _node_filter_values(NodeInventory.role, cluster_id)
    options = {
        _canonical_role_filter(value): _role_display(value)
        for value in values
        if _canonical_role_filter(value)
    }
    return [
        {'value': value, 'label': label}
        for value, label in sorted(options.items(), key=lambda item: item[1].lower())
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
    conditions = (
        (node.unschedulable, 'Cordoned'),
        (node.memory_pressure, 'Memory Pressure'),
        (node.disk_pressure, 'Disk Pressure'),
        (node.pid_pressure, 'PID Pressure'),
        (node.network_unavailable, 'Network Unavailable'),
    )
    return [label for value, label in conditions if _reported_true(value)]


def _node_condition_summary(labels: list[str], status: str | None) -> str:
    if not labels and status not in {'Ready', 'NotReady'}:
        return 'Readiness evidence incomplete'
    if not labels:
        return 'No active conditions'
    if len(labels) <= 2:
        return ' · '.join(labels)
    return f'{labels[0]} · {labels[1]} · +{len(labels) - 2} more'


def _node_inventory_query(cluster_id: str | None, role: str | None, status: str | None, search: str | None):
    query = db.session.query(
        NodeInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NodeInventory.cluster_id)
    query = filter_current_generation(query, NodeInventory)

    filters = []
    if cluster_id:
        filters.append(NodeInventory.cluster_id == cluster_id)
    if role == 'control-plane':
        filters.append(func.lower(NodeInventory.role).in_(('control-plane', 'master')))
    elif role:
        filters.append(NodeInventory.role == role)
    if status:
        filters.append(NodeInventory.status == status)
    if search:
        pattern = f'%{search}%'
        filters.append(
            db.or_(
                NodeInventory.node_name.ilike(pattern),
                NodeInventory.internal_ip.ilike(pattern),
                NodeInventory.external_ip.ilike(pattern),
                NodeInventory.hostname_address.ilike(pattern),
            )
        )
    return query.filter(*filters) if filters else query


def _scheduling_display(value: object, *, missing_label: str) -> str:
    if _reported_true(value):
        return 'Cordoned'
    if _reported_false(value):
        return 'Schedulable'
    return missing_label


def _network_scope(node: NodeInventory) -> str:
    if node.external_ip:
        return 'External Address Available'
    if node.internal_ip:
        return 'Private Node'
    return 'Address Not Reported'


def _node_table_row(node: NodeInventory, cluster_name: str, cluster_environment: str | None) -> dict[str, Any]:
    runtime = node.container_runtime or ''
    runtime_display = runtime.split('://')[0] if '://' in runtime else runtime
    node_status = node.status or 'Unknown'
    memory_display = format_kubernetes_size(node.memory)
    ephemeral_display = format_kubernetes_size(node.ephemeral_storage)
    condition_labels = _node_condition_labels(node)
    return {
        'id': node.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'node_name': node.node_name,
        'role_display': _role_display(node.role),
        'status_display': _status_display(node_status),
        'status_tone': _status_tone(node_status),
        'scheduling_display': _scheduling_display(node.unschedulable, missing_label='Scheduling Not Reported'),
        'condition_summary': _node_condition_summary(condition_labels, node_status),
        'condition_count': len(condition_labels),
        'internal_ip': node.internal_ip,
        'network_scope': _network_scope(node),
        'capacity_primary': ' · '.join(
            (
                f'{node.cpu} CPU' if node.cpu is not None else 'CPU Not Reported',
                memory_display if memory_display != '-' else 'Memory Not Reported',
            )
        ),
        'capacity_secondary': (
            f'{ephemeral_display} Ephemeral' if ephemeral_display != '-' else 'Ephemeral storage not reported'
        ),
        'identity_supporting': ' · '.join(value for value in (node.os_image, runtime_display) if value)
        or 'Platform details not reported',
    }


def _fleet_posture(
    *,
    total_nodes: int,
    not_ready_nodes: int,
    network_issue_nodes: int,
    pressure_nodes: int,
    cordoned_nodes: int,
    unknown_nodes: int,
    scheduling_unknown_nodes: int,
) -> tuple[str, str]:
    if total_nodes == 0:
        return 'unknown', 'No Data'
    if not_ready_nodes == total_nodes:
        fleet_posture_tone, fleet_posture_label = 'critical', 'Critical'
        return fleet_posture_tone, fleet_posture_label
    if not_ready_nodes > 0 or network_issue_nodes > 0 or pressure_nodes > 0 or cordoned_nodes > 0:
        return 'warning', 'Attention'
    if unknown_nodes > 0 or scheduling_unknown_nodes > 0:
        return 'unknown', 'Incomplete'
    return 'normal', 'Healthy'


def _node_summary(summary_rows: list[tuple[Any, ...]], total_nodes: int) -> dict[str, Any]:
    cpu_reported_nodes = sum(row[0] is not None for row in summary_rows)
    memory_reported_nodes = sum(format_kubernetes_size(row[1]) != '-' for row in summary_rows)
    ephemeral_reported_nodes = sum(format_kubernetes_size(row[2]) != '-' for row in summary_rows)
    ready_nodes = sum(row[3] == 'Ready' for row in summary_rows)
    not_ready_nodes = sum(row[3] == 'NotReady' for row in summary_rows)
    unknown_nodes = total_nodes - ready_nodes - not_ready_nodes
    cordoned_nodes = sum(_reported_true(row[4]) for row in summary_rows)
    scheduling_unknown_nodes = sum(row[4] is None for row in summary_rows)
    pressure_nodes = sum(any(_reported_true(value) for value in row[5:8]) for row in summary_rows)
    network_issue_nodes = sum(_reported_true(row[8]) for row in summary_rows)
    active_signal_nodes = sum(
        row[3] != 'Ready'
        or _reported_true(row[4])
        or row[4] is None
        or any(_reported_true(value) for value in row[5:8])
        or _reported_true(row[8])
        for row in summary_rows
    )
    fleet_posture_tone, fleet_posture_label = _fleet_posture(
        total_nodes=total_nodes,
        not_ready_nodes=not_ready_nodes,
        network_issue_nodes=network_issue_nodes,
        pressure_nodes=pressure_nodes,
        cordoned_nodes=cordoned_nodes,
        unknown_nodes=unknown_nodes,
        scheduling_unknown_nodes=scheduling_unknown_nodes,
    )
    total_cpu = sum(row[0] for row in summary_rows if row[0] is not None)
    total_memory = round(
        sum(convert_ki_to_gib(row[1]) for row in summary_rows if format_kubernetes_size(row[1]) != '-'),
        1,
    )
    total_ephemeral_storage = round(
        sum(convert_storage_to_gib(row[2]) for row in summary_rows if format_kubernetes_size(row[2]) != '-'),
        1,
    )
    return {
        'total_nodes': total_nodes,
        'ready_nodes': ready_nodes,
        'not_ready_nodes': not_ready_nodes,
        'unknown_nodes': unknown_nodes,
        'cordoned_nodes': cordoned_nodes,
        'scheduling_unknown_nodes': scheduling_unknown_nodes,
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
    }


def get_node_inventory(
    cluster_id=None,
    role=None,
    status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = _node_inventory_query(cluster_id, role, status, search)
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
    rows, pagination = paginate_query(
        query.order_by(Cluster.name, NodeInventory.node_name),
        page=page,
        per_page=per_page,
    )
    inventory = _node_summary(summary_rows, pagination['total_items'])
    inventory['nodes'] = [_node_table_row(*row) for row in rows]
    inventory['pagination'] = pagination
    return inventory


def _pressure_display(value: object) -> str:
    if _reported_true(value):
        return 'Pressure Detected'
    if _reported_false(value):
        return 'Normal'
    return 'Not Reported'


def _network_availability(value: object) -> str:
    if _reported_true(value):
        return 'Unavailable'
    if _reported_false(value):
        return 'Available'
    return 'Not Reported'


def _operational_context(
    *,
    ready_condition: str,
    network_availability: str,
    has_pressure: bool,
    scheduling_display: str,
) -> dict[str, str]:
    if ready_condition == 'Not Ready':
        return {
            'title': 'Investigate Node Readiness',
            'description': 'Review kubelet health, network availability, pressure conditions, and recent cluster events before rescheduling workloads.',
            'tone': 'critical',
            'icon': 'shield-alert',
        }
    if network_availability == 'Unavailable':
        return {
            'title': 'Restore Node Network Availability',
            'description': 'Confirm the node network path and CNI condition before relying on this node for workload placement.',
            'tone': 'critical',
            'icon': 'network-x',
        }
    if has_pressure:
        return {
            'title': 'Resolve Resource Pressure',
            'description': 'Review workload placement and resource consumption before the condition affects additional Pods.',
            'tone': 'warning',
            'icon': 'gauge',
        }
    if scheduling_display == 'Cordoned':
        return {
            'title': 'Review Scheduling Boundary',
            'description': 'The node is cordoned. Confirm whether this is planned maintenance before making it schedulable again.',
            'tone': 'warning',
            'icon': 'circle-pause',
        }
    if ready_condition == 'Unknown':
        return {
            'title': 'Validate Node Readiness Evidence',
            'description': 'Readiness is not reported in the committed snapshot. Confirm kubelet state and collection coverage before relying on this node for placement decisions.',
            'tone': 'unknown',
            'icon': 'circle-help',
        }
    if scheduling_display == 'Not Reported':
        return {
            'title': 'Validate Node Scheduling Evidence',
            'description': 'Scheduling state is not reported in the committed snapshot. Confirm the Node spec before treating this node as available for new Pod placement.',
            'tone': 'unknown',
            'icon': 'calendar-search',
        }
    return {
        'title': 'Node Ready for Scheduling',
        'description': 'No critical readiness, network, or pressure signal is present in the current committed inventory snapshot.',
        'tone': 'normal',
        'icon': 'circle-check',
    }


def _scheduled_pod_count(node: NodeInventory) -> int:
    query = filter_current_generation(db.session.query(func.count(PodInventory.id)), PodInventory)
    return int(
        query.filter(
            PodInventory.cluster_id == node.cluster_id,
            PodInventory.node_name == node.node_name,
        ).scalar()
        or 0
    )


def _capacity_detail(node: NodeInventory) -> dict[str, str]:
    cpu_display = f'{node.cpu} Cores' if node.cpu is not None else 'Not Reported'
    raw_values = {
        'memory_display': format_kubernetes_size(node.memory),
        'ephemeral_storage_display': format_kubernetes_size(node.ephemeral_storage),
        'ephemeral_storage_allocatable_display': format_kubernetes_size(node.ephemeral_storage_allocatable),
    }
    values = {key: value if value != '-' else 'Not Reported' for key, value in raw_values.items()}
    return {
        'cpu_display': cpu_display,
        'capacity_summary': f'{cpu_display} · {values["memory_display"]}',
        **values,
    }


def _platform_detail(node: NodeInventory) -> dict[str, str]:
    labels = node.labels or {}
    operating_system = node.operating_system or labels.get('kubernetes.io/os') or 'Unknown'
    operating_system_display = (
        operating_system.title() if operating_system.lower() in {'linux', 'windows'} else operating_system
    )
    return {
        'operating_system_display': operating_system_display,
        'architecture': node.architecture or labels.get('kubernetes.io/arch') or 'Not Reported',
    }


def get_node_detail(node_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        NodeInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NodeInventory.cluster_id)
    result = filter_current_generation(query, NodeInventory).filter(NodeInventory.id == node_id).first()
    if result is None:
        return None

    node, cluster_name, cluster_environment = result
    scheduling_display = _scheduling_display(node.unschedulable, missing_label='Not Reported')
    network_availability = _network_availability(node.network_unavailable)
    ready_condition = _status_display(node.status)
    pressures = {
        'memory_pressure': _pressure_display(node.memory_pressure),
        'disk_pressure': _pressure_display(node.disk_pressure),
        'pid_pressure': _pressure_display(node.pid_pressure),
    }
    has_pressure = 'Pressure Detected' in pressures.values()
    role = node.role or 'Unknown'
    labels = node.labels or {}
    runtime = node.container_runtime or ''

    return {
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'node_name': node.node_name,
        'system_uuid': node.system_uuid or 'Not Reported',
        'role_display': _role_display(role),
        'age': format_age(node.created_at),
        'role_description': NODE_ROLE_DESCRIPTIONS.get(
            role.lower(),
            'Provides Kubernetes node capacity. Its exact function depends on the labels and workloads assigned to it.',
        ),
        'status': node.status or 'Unknown',
        'status_display': _status_display(node.status),
        'internal_ip': node.internal_ip,
        'external_ip': node.external_ip,
        'hostname_address': node.hostname_address,
        'scheduled_pod_count': _scheduled_pod_count(node),
        'network_availability': network_availability,
        'network_scope': _network_scope(node),
        'scheduling_display': scheduling_display,
        'ready_condition': ready_condition,
        **pressures,
        'has_pressure': has_pressure,
        'taints': node.taints or [],
        'labels': dict(sorted(labels.items())),
        **_platform_detail(node),
        'kubelet_version': node.kubelet_version or 'Not Reported',
        'kube_proxy_version': node.kube_proxy_version or 'Not Reported',
        'cpu': node.cpu,
        **_capacity_detail(node),
        'os_image': node.os_image or 'Not Reported',
        'kernel_version': node.kernel_version or 'Not Reported',
        'container_runtime_identifier': runtime or 'Not Reported',
        'collected_at': node.collected_at,
        'operational_context': _operational_context(
            ready_condition=ready_condition,
            network_availability=network_availability,
            has_pressure=has_pressure,
            scheduling_display=scheduling_display,
        ),
    }
