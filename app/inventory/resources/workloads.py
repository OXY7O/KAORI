from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_

from app.extensions import db
from app.models import (
    Cluster, ConfigurationInventory, IngressInventory, NamespaceInventory,
    NodeInventory, PodInventory, ResourceQuotaInventory, ServiceInventory,
    StorageInventory, WorkloadInventory,
)

from app.inventory.resources.descriptions import WORKLOAD_TYPE_DESCRIPTIONS
from app.inventory.resources.common import (
    _display_boolean, _pod_summary, _selector_matches, _service_port_rows,
    _split_inventory_values, format_age,
)
from app.inventory.formatting import (
    convert_ki_to_gib, convert_storage_to_gib, format_byte_count,
    format_kubernetes_size, format_quota_value,
)

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


def _fallback_pod_template_from_associated_pods(
    related_pods: list[PodInventory],
) -> dict[str, Any]:
    """Provide a safe partial view for snapshots created by an older worker."""
    if not related_pods:
        return {}

    reference_pod = max(
        related_pods,
        key=lambda pod: len(pod.container_names or []) + len(pod.init_container_images or []),
    )
    container_names = list(reference_pod.container_names or [])
    container_images = list(reference_pod.container_images or [])
    init_images = list(reference_pod.init_container_images or [])
    containers: list[dict[str, str]] = []

    regular_count = max(len(container_names), len(container_images))
    for index in range(regular_count):
        containers.append(
            {
                'name': container_names[index] if index < len(container_names) else f'container-{index + 1}',
                'image': container_images[index] if index < len(container_images) else '-',
                'pull_policy': '-',
                'kind': 'Container',
            }
        )

    for index, image in enumerate(init_images):
        containers.append(
            {
                'name': f'init-container-{index + 1}',
                'image': image,
                'pull_policy': '-',
                'kind': 'Init container',
            }
        )

    return {
        'reported': False,
        'schema_version': 1,
        'source': 'associated-pod-fallback',
        'containers': containers,
        'container_count': regular_count,
        'init_container_count': len(init_images),
        'service_account': '-',
        'restart_policy': '-',
        'priority_class': '-',
        'scheduler': '-',
        'host_network': False,
        'dns_policy': '-',
        'volume_count': 0,
        'node_selector': {},
        'affinity_configured': False,
        'tolerations': [],
        'topology_spread_count': 0,
        'runtime_class': '-',
    }


def _pod_template_has_inventory_data(
    pod_template: dict[str, Any],
) -> bool:
    if pod_template.get('containers'):
        return True

    if int(pod_template.get('container_count') or 0) > 0:
        return True

    if int(pod_template.get('init_container_count') or 0) > 0:
        return True

    for key in (
        'service_account',
        'restart_policy',
        'priority_class',
        'scheduler',
        'dns_policy',
        'runtime_class',
    ):
        if pod_template.get(key) not in (None, '', '-'):
            return True

    return bool(
        pod_template.get('volume_count')
        or pod_template.get('node_selector')
        or pod_template.get('affinity_configured')
        or pod_template.get('tolerations')
        or pod_template.get('topology_spread_count')
    )


def _resolve_workload_pod_template(
    details: dict[str, Any],
    related_pods: list[PodInventory],
) -> tuple[dict[str, Any], str]:
    pod_template = details.get('pod_template')
    if isinstance(pod_template, dict) and (
        pod_template.get('reported') is True or _pod_template_has_inventory_data(pod_template)
    ):
        return pod_template, 'workload-template'

    fallback = _fallback_pod_template_from_associated_pods(related_pods)
    if fallback:
        return fallback, 'associated-pod-fallback'

    return {}, 'not-reported'


def _pod_configuration_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {'label': 'Containers', 'value': str(pod_template.get('container_count', 0))},
        {'label': 'Init containers', 'value': str(pod_template.get('init_container_count', 0))},
        {'label': 'Service account', 'value': str(pod_template.get('service_account') or '-')},
        {'label': 'Restart policy', 'value': str(pod_template.get('restart_policy') or '-')},
        {'label': 'Priority class', 'value': str(pod_template.get('priority_class') or '-')},
        {'label': 'Scheduler', 'value': str(pod_template.get('scheduler') or '-')},
        {'label': 'Host network', 'value': _display_boolean(pod_template.get('host_network'))},
        {'label': 'DNS policy', 'value': str(pod_template.get('dns_policy') or '-')},
        {'label': 'Volumes', 'value': str(pod_template.get('volume_count', 0))},
    ]


def _placement_rows(
    pod_template: dict[str, Any],
) -> list[dict[str, str]]:
    node_selector = pod_template.get('node_selector') or {}
    tolerations = pod_template.get('tolerations') or []

    return [
        {
            'label': 'Node selector',
            'value': f'{len(node_selector)} rule' + ('s' if len(node_selector) != 1 else ''),
        },
        {
            'label': 'Affinity',
            'value': 'Configured' if pod_template.get('affinity_configured') else 'Not configured',
        },
        {
            'label': 'Tolerations',
            'value': str(len(tolerations)),
        },
        {
            'label': 'Topology spread',
            'value': str(pod_template.get('topology_spread_count', 0)),
        },
        {
            'label': 'Runtime class',
            'value': str(pod_template.get('runtime_class') or '-'),
        },
    ]


def get_workload_detail(workload_id: int) -> dict[str, Any] | None:
    result = (
        db.session.query(
            WorkloadInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == WorkloadInventory.cluster_id)
        .filter(WorkloadInventory.id == workload_id)
        .first()
    )

    if result is None:
        return None

    workload, cluster_name = result
    workload_type = workload.workload_type or 'Unknown'
    details = workload.details or {}

    related_pods = (
        PodInventory.query.filter_by(
            cluster_id=workload.cluster_id,
            namespace=workload.namespace,
            workload_type=workload_type,
            workload_name=workload.name,
        )
        .order_by(PodInventory.pod_name)
        .all()
    )

    pod_template, pod_configuration_source = _resolve_workload_pod_template(
        details,
        related_pods,
    )

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
        row
        for row in placement_rows
        if row['value'] not in {'0', '0 rules', 'Not configured', '-'}
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
        'pod_configuration_reported': pod_configuration_source == 'workload-template',
        'pod_configuration_source': pod_configuration_source,
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


def _workload_update_strategy(
    workload_type: str,
    details: dict[str, Any],
) -> tuple[str, str]:
    if workload_type in {'Job', 'CronJob'}:
        return 'Not applicable', 'not_applicable'

    delivery_rows = details.get('delivery_rows') or []

    if not isinstance(delivery_rows, list):
        return 'Not reported', 'unknown'

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

    return 'Not reported', 'unknown'


def get_workload_inventory(
    cluster_id=None,
    namespace=None,
    workload_type=None,
    status=None,
    search=None,
):
    query = db.session.query(
        WorkloadInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == WorkloadInventory.cluster_id,
    )

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

    workloads = query.order_by(
        Cluster.name,
        WorkloadInventory.namespace,
        WorkloadInventory.name,
    ).all()

    pod_count_map: dict[tuple[str, str, str, str], int] = {}

    if workloads:
        cluster_ids = sorted({workload.cluster_id for workload, _ in workloads})

        pod_counts = (
            db.session.query(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.workload_type,
                PodInventory.workload_name,
                func.count(PodInventory.id),
            )
            .filter(PodInventory.cluster_id.in_(cluster_ids))
            .filter(PodInventory.workload_type.is_not(None))
            .filter(PodInventory.workload_name.is_not(None))
            .group_by(
                PodInventory.cluster_id,
                PodInventory.namespace,
                PodInventory.workload_type,
                PodInventory.workload_name,
            )
            .all()
        )

        pod_count_map = {
            (cluster_key, namespace, pod_workload_type, pod_workload_name): count
            for cluster_key, namespace, pod_workload_type, pod_workload_name, count in pod_counts
        }

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}

    deployments = 0
    statefulsets = 0
    daemonsets = 0
    jobs = 0
    cronjobs = 0

    workloads_data = []

    for workload, cluster_name in workloads:
        current_type = workload.workload_type or 'Unknown'
        status_name = workload.status or 'Unknown'
        details = workload.details or {}
        pod_template = details.get('pod_template') or {}

        type_counts[current_type] = type_counts.get(current_type, 0) + 1
        status_counts[status_name] = status_counts.get(status_name, 0) + 1

        if current_type == 'Deployment':
            deployments += 1
        elif current_type == 'StatefulSet':
            statefulsets += 1
        elif current_type == 'DaemonSet':
            daemonsets += 1
        elif current_type == 'Job':
            jobs += 1
        elif current_type == 'CronJob':
            cronjobs += 1

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
        'total_workloads': len(workloads),
        'deployments': deployments,
        'statefulsets': statefulsets,
        'daemonsets': daemonsets,
        'jobs': jobs,
        'cronjobs': cronjobs,
        'type_counts': type_counts,
        'status_counts': status_counts,
        'namespaces': get_workload_filter_namespaces(
            cluster_id=cluster_id,
        ),
        'workload_types': get_workload_filter_types(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'workload_statuses': get_workload_filter_statuses(
            cluster_id=cluster_id,
            namespace=namespace,
        ),
        'workloads': workloads_data,
    }


