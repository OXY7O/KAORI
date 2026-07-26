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


def _workload_detail_rows(
    details: dict[str, Any],
    key: str,
) -> list[dict[str, str]]:
    rows = details.get(key) or []
    return [
        {
            'label': str(row.get('label') or '-'),
            'value': str(row.get('value') if row.get('value') not in (None, '') else '-'),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _compact_runtime_state_rows(
    workload_type: str,
    rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    preferred_labels = {
        'Deployment': ('Desired replicas', 'Ready replicas', 'Available replicas', 'Unavailable replicas'),
        'StatefulSet': ('Desired replicas', 'Ready replicas', 'Available replicas', 'Current revision'),
        'DaemonSet': ('Desired scheduled', 'Ready', 'Available', 'Unavailable'),
        'Job': ('Completions', 'Active', 'Succeeded', 'Failed'),
        'CronJob': ('Schedule', 'Suspended', 'Active Jobs', 'Last schedule'),
    }
    preferred = preferred_labels.get(workload_type, ())
    indexed = {str(row.get('label')): row for row in rows}
    compact = [indexed[label] for label in preferred if label in indexed]
    fallback = [row for row in rows if row.get('label') != 'Managed Pods'][:4]
    return compact or fallback


def _workload_pod_template(details: dict[str, Any]) -> dict[str, Any]:
    pod_template = details.get('pod_template')
    if isinstance(pod_template, dict) and pod_template.get('reported') is True:
        return pod_template

    return {}


def _pod_configuration_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
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
    ]


def _placement_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []

    return [
        {
            'label': 'Node Selector',
            'value': f'{len(node_selector)} rule' + ('s' if len(node_selector) != 1 else ''),
        },
        {
            'label': 'Affinity',
            'value': 'Configured' if pod_template.get('affinity_configured') else 'Not Configured',
        },
        {
            'label': 'Tolerations',
            'value': str(len(tolerations)),
        },
        {
            'label': 'Topology Spread',
            'value': str(pod_template.get('topology_spread_count', 0)),
        },
        {
            'label': 'Runtime Class',
            'value': str(pod_template.get('runtime_class') or '-'),
        },
    ]


def get_workload_detail(workload_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        WorkloadInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == WorkloadInventory.cluster_id)
    query = filter_current_generation(query, WorkloadInventory)
    result = query.filter(WorkloadInventory.id == workload_id).first()

    if result is None:
        return None

    workload, cluster_name = result
    workload_type = workload.workload_type or 'Unknown'
    details = workload.details or {}

    related_pods = (
        filter_current_generation(PodInventory.query, PodInventory)
        .filter_by(
            cluster_id=workload.cluster_id,
            namespace=workload.namespace,
            workload_type=workload_type,
            workload_name=workload.name,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )

    pod_template = _workload_pod_template(details)

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
            {'label': 'Managed Pods', 'value': str(len(related_pods))},
        ]

    delivery_rows = _workload_detail_rows(details, 'delivery_rows')
    placement_rows = _placement_rows(pod_template)
    placement_summary_rows = [
        row for row in placement_rows if row['value'] not in {'0', '0 Rules', 'Not Configured', '-'}
    ]

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
        'placement_summary_rows': placement_summary_rows,
        'placement_constraint_count': (
            len(node_selector)
            + len(tolerations)
            + (1 if pod_template.get('affinity_configured') else 0)
            + int(pod_template.get('topology_spread_count') or 0)
        ),
        'placement_configured': bool(
            node_selector
            or tolerations
            or pod_template.get('affinity_configured')
            or pod_template.get('topology_spread_count')
        ),
        'node_selectors': [f'{key}={value}' for key, value in sorted(node_selector.items())],
        'tolerations': [str(item) for item in tolerations],
        'containers': containers,
        'container_count': int(pod_template.get('container_count') or 0),
        'init_container_count': int(pod_template.get('init_container_count') or 0),
        'pod_count': len(related_pods),
        'pods': [_pod_summary(pod) for pod in related_pods[:8]],
        'pods_truncated': len(related_pods) > 8,
        'labels': sorted(labels.items()),
        'annotations': sorted(annotations.items()),
    }


def get_workload_filter_namespaces(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.namespace,
    )
    query = filter_current_generation(query, WorkloadInventory)

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.namespace,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_workload_filter_types(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.workload_type,
    )
    query = filter_current_generation(query, WorkloadInventory)

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            WorkloadInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.workload_type,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_workload_filter_statuses(
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> list[str]:
    query = db.session.query(
        WorkloadInventory.status,
    )
    query = filter_current_generation(query, WorkloadInventory)

    if cluster_id:
        query = query.filter(
            WorkloadInventory.cluster_id == cluster_id,
        )

    if namespace:
        query = query.filter(
            WorkloadInventory.namespace == namespace,
        )

    rows = (
        query.distinct()
        .order_by(
            WorkloadInventory.status,
        )
        .all()
    )

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


def _workload_update_strategy(
    workload_type: str,
    details: dict[str, Any],
) -> tuple[str, str]:
    if workload_type in {'Job', 'CronJob'}:
        return 'Not applicable', 'not_applicable'

    delivery_rows = details.get('delivery_rows') or []

    if not isinstance(delivery_rows, list):
        return 'Not Reported', 'unknown'

    for row in delivery_rows:
        if not isinstance(row, dict):
            continue

        label = str(row.get('label') or '').strip().lower()

        if label not in {'strategy', 'update strategy'}:
            continue

        raw_value = str(row.get('value') or '').strip()

        if not raw_value or raw_value in {'-', 'None'}:
            break

        normalized_value = raw_value.replace(' ', '').lower()

        return _WORKLOAD_UPDATE_STRATEGIES.get(
            normalized_value,
            (raw_value, 'other'),
        )

    return 'Not Reported', 'unknown'


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
        Cluster.name.label(
            'cluster_name',
        ),
        Cluster.environment.label(
            'cluster_environment',
        ),
    ).join(
        Cluster,
        Cluster.id == WorkloadInventory.cluster_id,
    )
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

    summary_rows = query.with_entities(
        WorkloadInventory.workload_type,
        WorkloadInventory.status,
    ).all()
    workloads, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            WorkloadInventory.namespace,
            WorkloadInventory.name,
        ),
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
    status_counts: dict[str, int] = {}
    for summary_type, summary_status in summary_rows:
        normalized_type = summary_type or 'Unknown'
        normalized_status = summary_status or 'Unknown'
        type_counts[normalized_type] = type_counts.get(normalized_type, 0) + 1
        status_counts[normalized_status] = status_counts.get(normalized_status, 0) + 1

    workloads_data = []
    for workload, cluster_name, cluster_environment in workloads:
        current_type = workload.workload_type or 'Unknown'
        status_name = workload.status or 'Unknown'
        details = workload.details or {}
        pod_template = _workload_pod_template(details)

        pod_count = pod_count_map.get(
            (
                workload.cluster_id,
                workload.namespace,
                current_type,
                workload.name,
            ),
            0,
        )

        update_strategy, update_strategy_key = _workload_update_strategy(
            current_type,
            details,
        )

        workloads_data.append(
            {
                'id': workload.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': workload.namespace,
                'name': workload.name,
                'type': current_type,
                'ready': workload.ready,
                'status': status_name,
                'state_display': details.get('state_display') or workload.ready or status_name,
                'pod_count': pod_count,
                'update_strategy': update_strategy,
                'update_strategy_key': update_strategy_key,
                'container_count': int(pod_template.get('container_count') or 0),
                'init_container_count': int(pod_template.get('init_container_count') or 0),
                'age': format_age(
                    workload.created_at,
                ),
                'created_at': workload.created_at,
                'collected_at': workload.collected_at,
            }
        )

    return {
        'total_workloads': pagination['total_items'],
        'deployments': type_counts.get('Deployment', 0),
        'statefulsets': type_counts.get('StatefulSet', 0),
        'daemonsets': type_counts.get('DaemonSet', 0),
        'jobs': type_counts.get('Job', 0),
        'cronjobs': type_counts.get('CronJob', 0),
        'type_counts': type_counts,
        'status_counts': status_counts,
        'workloads': workloads_data,
        'pagination': pagination,
    }
