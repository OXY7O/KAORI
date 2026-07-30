from __future__ import annotations

from typing import Any

from sqlalchemy import func, tuple_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.resources.common import _display_boolean, _pod_summary, format_age
from app.inventory.resources.descriptions import WORKLOAD_TYPE_DESCRIPTIONS
from app.models import Cluster, PodInventory, WorkloadInventory

_WORKLOAD_UPDATE_STRATEGIES = {
    'rollingupdate': ('Rolling Update', 'rolling_update'),
    'recreate': ('Recreate', 'recreate'),
    'ondelete': ('On Delete', 'on_delete'),
}

_OPERATIONAL_STATES = {
    'running': ('Stable', 'normal'),
    'progressing': ('Progressing', 'pending'),
    'failed': ('Failed', 'critical'),
    'suspended': ('Suspended', 'info'),
}


def _workload_detail_rows(details: dict[str, Any], key: str) -> list[dict[str, str]]:
    rows = details.get(key) or []
    return [
        {
            'label': str(row.get('label') or '-'),
            'value': str(row.get('value') if row.get('value') not in (None, '') else '-'),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _row_value(rows: list[dict[str, str]], *labels: str, default: str = '-') -> str:
    wanted = {label.casefold() for label in labels}
    for row in rows:
        if str(row.get('label') or '').casefold() in wanted:
            value = str(row.get('value') or '').strip()
            return value if value and value not in {'None'} else default
    return default


def _compact_runtime_state_rows(workload_type: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    preferred_labels = {
        'Deployment': ('Desired Replicas', 'Updated Replicas', 'Ready Replicas', 'Available Replicas', 'Unavailable Replicas'),
        'StatefulSet': ('Desired Replicas', 'Updated Replicas', 'Ready Replicas', 'Available Replicas', 'Current Revision'),
        'DaemonSet': ('Desired Scheduled', 'Ready', 'Available', 'Unavailable', 'Misscheduled'),
        'Job': ('Completions', 'Active', 'Succeeded', 'Failed', 'Backoff Limit'),
        'CronJob': ('Schedule', 'Suspended', 'Active Jobs', 'Last Schedule', 'Last Successful Execution'),
    }
    preferred = {label.casefold() for label in preferred_labels.get(workload_type, ())}
    compact = [row for row in rows if str(row.get('label') or '').casefold() in preferred]
    fallback = [row for row in rows if str(row.get('label') or '').casefold() != 'managed pods'][:5]
    return compact or fallback


def _workload_pod_template(details: dict[str, Any]) -> dict[str, Any]:
    pod_template = details.get('pod_template')
    if isinstance(pod_template, dict) and pod_template.get('reported') is True:
        return pod_template
    return {}


def _pod_configuration_rows(pod_template: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {'label': 'Containers', 'value': str(pod_template.get('container_count', 0))},
        {'label': 'Init Containers', 'value': str(pod_template.get('init_container_count', 0))},
        {'label': 'Service Account', 'value': str(pod_template.get('service_account') or '-')},
        {'label': 'Restart Policy', 'value': str(pod_template.get('restart_policy') or '-')},
        {'label': 'Priority Class', 'value': str(pod_template.get('priority_class') or '-')},
        {'label': 'Scheduler', 'value': str(pod_template.get('scheduler') or '-')},
        {'label': 'Host Network', 'value': _display_boolean(pod_template.get('host_network'))},
        {'label': 'DNS Policy', 'value': str(pod_template.get('dns_policy') or '-')},
        {'label': 'Volumes', 'value': str(pod_template.get('volume_count', 0))},
        {'label': 'Runtime Class', 'value': str(pod_template.get('runtime_class') or '-')},
    ]


def _placement_rows(pod_template: dict[str, Any]) -> list[dict[str, str]]:
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []
    return [
        {'label': 'Node Selector', 'value': f'{len(node_selector)} rule' + ('s' if len(node_selector) != 1 else '')},
        {'label': 'Affinity', 'value': 'Configured' if pod_template.get('affinity_configured') else 'Not Configured'},
        {'label': 'Tolerations', 'value': str(len(tolerations))},
        {'label': 'Topology Spread', 'value': str(pod_template.get('topology_spread_count', 0))},
        {'label': 'Runtime Class', 'value': str(pod_template.get('runtime_class') or '-')},
    ]


def _operational_state(status: str | None) -> tuple[str, str]:
    return _OPERATIONAL_STATES.get(str(status or '').strip().casefold(), ('Unknown', 'unknown'))


def _pod_tone(status: str | None) -> str:
    normalized = str(status or '').casefold()
    if normalized in {'running', 'succeeded'}:
        return 'normal'
    if normalized == 'pending':
        return 'pending'
    if normalized == 'failed':
        return 'critical'
    return 'unknown'


def _workload_update_strategy(workload_type: str, details: dict[str, Any]) -> tuple[str, str]:
    if workload_type in {'Job', 'CronJob'}:
        return 'Not Applicable', 'not_applicable'
    delivery_rows = details.get('delivery_rows') or []
    if not isinstance(delivery_rows, list):
        return 'Not Reported', 'unknown'
    for row in delivery_rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get('label') or '').strip().casefold()
        if label not in {'strategy', 'update strategy'}:
            continue
        raw_value = str(row.get('value') or '').strip()
        if not raw_value or raw_value in {'-', 'None'}:
            break
        normalized_value = raw_value.replace(' ', '').casefold()
        return _WORKLOAD_UPDATE_STRATEGIES.get(normalized_value, (raw_value, 'other'))
    return 'Not Reported', 'unknown'


def _delivery_model(workload_type: str, details: dict[str, Any], placement_count: int = 0) -> tuple[str, str]:
    state_rows = _workload_detail_rows(details, 'state_rows')
    delivery_rows = _workload_detail_rows(details, 'delivery_rows')
    if workload_type == 'Job':
        backoff = _row_value(delivery_rows, 'Backoff Limit')
        return 'Job Execution', f'Backoff Limit {backoff}' if backoff != '-' else 'Batch completion policy'
    if workload_type == 'CronJob':
        schedule = _row_value(state_rows, 'Schedule')
        return 'Scheduled Execution', schedule if schedule != '-' else 'Schedule not reported'
    strategy, _ = _workload_update_strategy(workload_type, details)
    support = f'{placement_count} Placement Constraint' + ('s' if placement_count != 1 else '')
    return strategy, support


def _overall_posture(total: int, counts: dict[str, int]) -> tuple[str, str]:
    if total == 0:
        return 'No Data', 'unknown'
    if counts.get('failed', 0) > 0:
        return 'Critical', 'critical'
    if counts.get('unknown', 0) > 0:
        return 'Review Required', 'warning'
    if counts.get('progressing', 0) > 0:
        return 'Progressing', 'pending'
    if counts.get('stable', 0) == 0 and counts.get('suspended', 0) > 0:
        return 'Paused', 'info'
    return 'Stable', 'normal'


def _operational_context(
    state_label: str,
    pod_count: int,
    pod_template_reported: bool,
) -> dict[str, str]:
    if state_label == 'Failed':
        return {
            'title': 'Investigate Workload Failure',
            'description': 'Review controller conditions, failed Pods, image delivery, placement constraints, and recent rollout changes.',
            'icon': 'circle-x',
            'tone': 'critical',
        }
    if state_label == 'Progressing':
        return {
            'title': 'Validate Rollout Progress',
            'description': 'Confirm updated and available replicas continue moving toward the desired state within the configured deadline.',
            'icon': 'loader-circle',
            'tone': 'warning',
        }
    if state_label == 'Suspended':
        return {
            'title': 'Confirm Planned Suspension',
            'description': 'Verify that the workload pause is intentional before resuming scheduled or batch execution.',
            'icon': 'circle-pause',
            'tone': 'info',
        }
    if pod_count == 0:
        return {
            'title': 'Review Workload Ownership',
            'description': 'No associated Pods are represented in the committed snapshot. Confirm rollout state and controller ownership.',
            'icon': 'git-branch',
            'tone': 'warning',
        }
    if not pod_template_reported:
        return {
            'title': 'Refresh Workload Template Evidence',
            'description': 'Pod template evidence has not been reported. Refresh inventory before reviewing delivery and placement configuration.',
            'icon': 'refresh-cw',
            'tone': 'warning',
        }
    return {
        'title': 'Workload Snapshot Ready for Review',
        'description': 'No exceptional delivery or runtime signal is present in the current committed inventory snapshot.',
        'icon': 'circle-check',
        'tone': 'normal',
    }


def get_workload_detail(workload_id: int) -> dict[str, Any] | None:
    query = db.session.query(WorkloadInventory, Cluster.name.label('cluster_name')).join(
        Cluster, Cluster.id == WorkloadInventory.cluster_id
    )
    query = filter_current_generation(query, WorkloadInventory)
    result = query.filter(WorkloadInventory.id == workload_id).first()
    if result is None:
        return None

    workload, cluster_name = result
    workload_type = workload.workload_type or 'Unknown'
    details = workload.details or {}
    pod_template = _workload_pod_template(details)

    related_query = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=workload.cluster_id,
        namespace=workload.namespace,
        workload_type=workload_type,
        workload_name=workload.name,
    )
    related_pod_count = related_query.count()
    related_pods = related_query.order_by(PodInventory.pod_name).limit(8).all()

    labels = details.get('labels') or {}
    annotations = details.get('annotations') or {}
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []
    containers = pod_template.get('containers') or []

    state_rows = _workload_detail_rows(details, 'state_rows')
    if not state_rows:
        state_rows = [
            {'label': 'Ready', 'value': workload.ready or '-'},
            {'label': 'Status', 'value': workload.status or 'Unknown'},
            {'label': 'Managed Pods', 'value': str(related_pod_count)},
        ]

    delivery_rows = _workload_detail_rows(details, 'delivery_rows')
    placement_rows = _placement_rows(pod_template)
    placement_constraint_count = (
        len(node_selector)
        + len(tolerations)
        + (1 if pod_template.get('affinity_configured') else 0)
        + int(pod_template.get('topology_spread_count') or 0)
    )
    delivery_model, delivery_supporting = _delivery_model(workload_type, details, placement_constraint_count)
    state_label, state_tone = _operational_state(workload.status)
    template_containers = int(pod_template.get('container_count') or 0) + int(
        pod_template.get('init_container_count') or 0
    )

    pods = []
    for pod in related_pods:
        item = _pod_summary(pod)
        item['status_tone'] = _pod_tone(item.get('status'))
        item['supporting_primary'] = f"Node {item.get('node') or '-'} · Ready {item.get('ready') or '-'}"
        item['supporting_secondary'] = f"{item.get('container_count', 0)} Containers · Age {item.get('age') or '-'}"
        pods.append(item)

    return {
        'id': workload.id,
        'cluster_id': workload.cluster_id,
        'cluster_name': cluster_name,
        'namespace': workload.namespace,
        'name': workload.name,
        'type': workload_type,
        'type_description': WORKLOAD_TYPE_DESCRIPTIONS.get(
            workload_type,
            'Represents a Kubernetes workload controller or batch resource that manages Pods.',
        ),
        'uid': details.get('uid') or '-',
        'ready': workload.ready or '-',
        'status': workload.status or 'Unknown',
        'operational_state_label': state_label,
        'operational_state_tone': state_tone,
        'state_display': details.get('state_display') or workload.ready or workload.status or 'Unknown',
        'age': format_age(workload.created_at),
        'created_at': workload.created_at,
        'collected_at': workload.collected_at,
        'state_rows': state_rows,
        'runtime_state_rows': _compact_runtime_state_rows(workload_type, state_rows),
        'pod_configuration_rows': _pod_configuration_rows(pod_template),
        'pod_configuration_reported': bool(pod_template),
        'delivery_rows': delivery_rows,
        'placement_rows': placement_rows,
        'placement_constraint_count': placement_constraint_count,
        'node_selectors': dict(sorted(node_selector.items())),
        'tolerations': {str(index + 1): str(item) for index, item in enumerate(tolerations)},
        'containers': containers,
        'container_count': int(pod_template.get('container_count') or 0),
        'init_container_count': int(pod_template.get('init_container_count') or 0),
        'template_container_count': template_containers,
        'delivery_model': delivery_model,
        'delivery_supporting': delivery_supporting,
        'pod_count': related_pod_count,
        'pods': pods,
        'pods_truncated': related_pod_count > len(pods),
        'labels': dict(sorted(labels.items())),
        'annotations': dict(sorted(annotations.items())),
        'operational_context': _operational_context(state_label, related_pod_count, bool(pod_template)),
    }


def get_workload_filter_namespaces(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(WorkloadInventory.namespace)
    query = filter_current_generation(query, WorkloadInventory)
    if cluster_id:
        query = query.filter(WorkloadInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(WorkloadInventory.namespace).all()
    return [row[0] for row in rows if row[0]]


def get_workload_filter_types(cluster_id: str | None = None, namespace: str | None = None) -> list[str]:
    query = db.session.query(WorkloadInventory.workload_type)
    query = filter_current_generation(query, WorkloadInventory)
    if cluster_id:
        query = query.filter(WorkloadInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(WorkloadInventory.namespace == namespace)
    rows = query.distinct().order_by(WorkloadInventory.workload_type).all()
    return [row[0] for row in rows if row[0]]


def get_workload_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
    workload_type: str | None = None,
) -> list[str]:
    query = db.session.query(WorkloadInventory.status)
    query = filter_current_generation(query, WorkloadInventory)
    if cluster_id:
        query = query.filter(WorkloadInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(WorkloadInventory.namespace == namespace)
    if workload_type:
        query = query.filter(WorkloadInventory.workload_type == workload_type)
    rows = query.distinct().order_by(WorkloadInventory.status).all()
    return [row[0] for row in rows if row[0]]


def _workload_pod_count_query():
    query = db.session.query(
        PodInventory.cluster_id,
        PodInventory.namespace,
        PodInventory.workload_type,
        PodInventory.workload_name,
        func.count(PodInventory.id),
    )
    return filter_current_generation(query, PodInventory)


def get_workload_inventory(
    cluster_id=None,
    namespace=None,
    workload_type=None,
    status=None,
    search=None,
    page: int = 1,
    per_page: int = 5,
):
    query = db.session.query(
        WorkloadInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == WorkloadInventory.cluster_id)
    query = filter_current_generation(query, WorkloadInventory)

    if cluster_id:
        query = query.filter(WorkloadInventory.cluster_id == cluster_id)
    if namespace:
        query = query.filter(WorkloadInventory.namespace == namespace)
    if workload_type:
        query = query.filter(WorkloadInventory.workload_type == workload_type)
    if status:
        query = query.filter(WorkloadInventory.status == status)
    if search:
        query = query.filter(WorkloadInventory.name.ilike(f'%{search}%'))

    summary_rows = (
        query.with_entities(
            WorkloadInventory.workload_type,
            WorkloadInventory.status,
            func.count(WorkloadInventory.id),
        )
        .group_by(WorkloadInventory.workload_type, WorkloadInventory.status)
        .all()
    )
    workloads, pagination = paginate_query(
        query.order_by(Cluster.name, WorkloadInventory.namespace, WorkloadInventory.name),
        page=page,
        per_page=per_page,
    )

    workload_keys = [
        (workload.cluster_id, workload.namespace, workload.workload_type, workload.name)
        for workload, _, _ in workloads
        if workload.workload_type
    ]
    pod_count_map: dict[tuple[str, str, str, str], int] = {}
    if workload_keys:
        pod_counts = (
            _workload_pod_count_query()
            .filter(
                tuple_(
                    PodInventory.cluster_id,
                    PodInventory.namespace,
                    PodInventory.workload_type,
                    PodInventory.workload_name,
                ).in_(workload_keys)
            )
            .group_by(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.workload_type,
                PodInventory.workload_name,
            )
            .all()
        )
        pod_count_map = {
            (cluster_key, pod_namespace, pod_workload_type, pod_workload_name): count
            for cluster_key, pod_namespace, pod_workload_type, pod_workload_name, count in pod_counts
        }

    type_counts: dict[str, int] = {}
    raw_status_counts: dict[str, int] = {}
    posture_counts = {'stable': 0, 'progressing': 0, 'failed': 0, 'suspended': 0, 'unknown': 0}
    for summary_type, summary_status, count in summary_rows:
        normalized_type = summary_type or 'Unknown'
        normalized_status = summary_status or 'Unknown'
        type_counts[normalized_type] = type_counts.get(normalized_type, 0) + int(count)
        raw_status_counts[normalized_status] = raw_status_counts.get(normalized_status, 0) + int(count)
        state_label, _ = _operational_state(normalized_status)
        posture_counts[state_label.casefold().replace(' ', '_')] = posture_counts.get(
            state_label.casefold().replace(' ', '_'), 0
        ) + int(count)

    total = pagination['total_items']
    posture_label, posture_tone = _overall_posture(total, posture_counts)

    workloads_data = []
    for workload, cluster_name, cluster_environment in workloads:
        current_type = workload.workload_type or 'Unknown'
        status_name = workload.status or 'Unknown'
        details = workload.details or {}
        pod_template = _workload_pod_template(details)
        pod_count = pod_count_map.get((workload.cluster_id, workload.namespace, current_type, workload.name), 0)
        state_label, state_tone = _operational_state(status_name)
        placement_count = (
            len(pod_template.get('node_selector') or {})
            + len(pod_template.get('tolerations') or [])
            + (1 if pod_template.get('affinity_configured') else 0)
            + int(pod_template.get('topology_spread_count') or 0)
        )
        delivery_model, delivery_supporting = _delivery_model(current_type, details, placement_count)
        container_count = int(pod_template.get('container_count') or 0)
        init_container_count = int(pod_template.get('init_container_count') or 0)
        workloads_data.append(
            {
                'id': workload.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': workload.namespace,
                'name': workload.name,
                'type': current_type,
                'identity_supporting': f'{current_type} · {format_age(workload.created_at)}',
                'ready': workload.ready,
                'status': status_name,
                'operational_state_label': state_label,
                'operational_state_tone': state_tone,
                'state_display': details.get('state_display') or workload.ready or status_name,
                'pod_count': pod_count,
                'runtime_primary': f'{pod_count} Managed ' + ('Pod' if pod_count == 1 else 'Pods'),
                'runtime_secondary': f'{container_count} Containers · {init_container_count} Init',
                'delivery_model': delivery_model,
                'delivery_supporting': delivery_supporting,
                'age': format_age(workload.created_at),
                'created_at': workload.created_at,
                'collected_at': workload.collected_at,
            }
        )

    controller_count = sum(type_counts.get(item, 0) for item in ('Deployment', 'StatefulSet', 'DaemonSet'))
    batch_count = sum(type_counts.get(item, 0) for item in ('Job', 'CronJob'))
    exception_count = posture_counts.get('progressing', 0) + posture_counts.get('failed', 0) + posture_counts.get('unknown', 0)

    return {
        'total_workloads': total,
        'deployments': type_counts.get('Deployment', 0),
        'statefulsets': type_counts.get('StatefulSet', 0),
        'daemonsets': type_counts.get('DaemonSet', 0),
        'jobs': type_counts.get('Job', 0),
        'cronjobs': type_counts.get('CronJob', 0),
        'workload_type_count': len([key for key, value in type_counts.items() if value > 0]),
        'controller_workloads': controller_count,
        'batch_workloads': batch_count,
        'stable_workloads': posture_counts.get('stable', 0),
        'progressing_workloads': posture_counts.get('progressing', 0),
        'failed_workloads': posture_counts.get('failed', 0),
        'suspended_workloads': posture_counts.get('suspended', 0),
        'unknown_workloads': posture_counts.get('unknown', 0),
        'exception_workloads': exception_count,
        'posture_label': posture_label,
        'posture_tone': posture_tone,
        'type_counts': type_counts,
        'status_counts': raw_status_counts,
        'workloads': workloads_data,
        'pagination': pagination,
    }
