from __future__ import annotations

from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.inventory.formatting import format_quota_value
from app.inventory.resources.common import filter_current_generation, format_age
from app.models import (
    Cluster,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    PodInventory,
    ResourceQuotaInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)


def get_namespace_filter_statuses(
    cluster_id: str | None = None,
) -> list[str]:
    query = db.session.query(
        NamespaceInventory.status,
    )

    if cluster_id:
        query = query.filter(
            NamespaceInventory.cluster_id == cluster_id,
        )

    rows = (
        query.distinct()
        .order_by(
            NamespaceInventory.status,
        )
        .all()
    )

    return [row[0] for row in rows if row[0]]


def get_namespace_inventory(
    cluster_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    query = db.session.query(
        NamespaceInventory,
        Cluster.name.label(
            'cluster_name',
        ),
    ).join(
        Cluster,
        Cluster.id == NamespaceInventory.cluster_id,
    )
    query = filter_current_generation(query, NamespaceInventory)

    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)

    if status:
        query = query.filter(NamespaceInventory.status == status)

    if search:
        query = query.filter(NamespaceInventory.namespace.ilike(f'%{search}%'))

    namespace_records = query.order_by(
        Cluster.name,
        NamespaceInventory.namespace,
    ).all()

    def _namespace_count_map(model) -> dict[tuple[str, str], int]:
        count_query = db.session.query(
            model.cluster_id,
            model.namespace,
            func.count(model.id),
        )

        if cluster_id:
            count_query = count_query.filter(model.cluster_id == cluster_id)

        return {
            (row_cluster_id, row_namespace): count
            for row_cluster_id, row_namespace, count in (
                count_query.group_by(
                    model.cluster_id,
                    model.namespace,
                ).all()
            )
        }

    workload_counts = _namespace_count_map(WorkloadInventory)
    pod_counts = _namespace_count_map(PodInventory)
    service_counts = _namespace_count_map(ServiceInventory)
    quota_counts = _namespace_count_map(ResourceQuotaInventory)

    status_counts: dict[str, int] = {}
    inventory_rows: list[dict[str, Any]] = []

    for namespace, cluster_name in namespace_records:
        namespace_status = namespace.status or 'Unknown'
        status_counts[namespace_status] = status_counts.get(namespace_status, 0) + 1

        key = (
            namespace.cluster_id,
            namespace.namespace,
        )
        quota_count = quota_counts.get(key, 0)
        limit_range_count = namespace.limit_range_count
        network_policy_count = namespace.network_policy_count

        inventory_rows.append(
            {
                'id': namespace.id,
                'cluster_name': cluster_name,
                'namespace': namespace.namespace,
                'status': namespace_status,
                'age': format_age(namespace.created_at),
                'workload_count': workload_counts.get(key, 0),
                'pod_count': pod_counts.get(key, 0),
                'service_count': service_counts.get(key, 0),
                'quota_count': quota_count,
                'limit_range_count': limit_range_count,
                'network_policy_count': network_policy_count,
                'controls_reported': (limit_range_count is not None and network_policy_count is not None),
            }
        )

    cluster_count = len({cluster_name for _, cluster_name in namespace_records})

    return {
        'total_namespaces': len(namespace_records),
        'total_clusters': cluster_count,
        'active_namespaces': status_counts.get('Active', 0),
        'status_counts': status_counts,
        'namespace_statuses': get_namespace_filter_statuses(
            cluster_id=cluster_id,
        ),
        'namespaces': inventory_rows,
    }


def get_namespace_detail(
    namespace_id: int,
) -> dict[str, Any] | None:
    result = (
        db.session.query(
            NamespaceInventory,
            Cluster.name.label('cluster_name'),
        )
        .join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
        .filter(NamespaceInventory.id == namespace_id)
        .first()
    )

    if result is None:
        return None

    namespace, cluster_name = result

    workload_counts = {
        workload_type or 'Unknown': count
        for workload_type, count in (
            db.session.query(
                WorkloadInventory.workload_type,
                func.count(WorkloadInventory.id),
            )
            .filter(
                WorkloadInventory.cluster_id == namespace.cluster_id,
                WorkloadInventory.namespace == namespace.namespace,
            )
            .group_by(WorkloadInventory.workload_type)
            .all()
        )
    }

    object_counts = {
        'workloads': WorkloadInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'pods': PodInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'services': ServiceInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'ingresses': IngressInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
        'persistent_volume_claims': StorageInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            storage_type='PersistentVolumeClaim',
        ).count(),
        'config_maps': ConfigurationInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            object_type='ConfigMap',
        ).count(),
        'secrets': ConfigurationInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
            object_type='Secret',
        ).count(),
        'resource_quotas': ResourceQuotaInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        ).count(),
    }

    object_counts['tracked_total'] = sum(
        object_counts[key]
        for key in (
            'workloads',
            'pods',
            'services',
            'ingresses',
            'persistent_volume_claims',
            'config_maps',
            'secrets',
        )
    )

    quota_rows = (
        ResourceQuotaInventory.query.filter_by(
            cluster_id=namespace.cluster_id,
            namespace=namespace.namespace,
        )
        .order_by(ResourceQuotaInventory.name)
        .all()
    )

    quotas: list[dict[str, Any]] = []

    for quota in quota_rows:
        resources = []

        for resource_name in sorted((quota.hard or {}).keys()):
            resources.append(
                {
                    'name': resource_name,
                    'hard': format_quota_value(
                        resource_name,
                        (quota.hard or {}).get(resource_name),
                    ),
                }
            )

        quotas.append(
            {
                'name': quota.name,
                'resources': resources[:10],
                'resource_count': len(resources),
                'truncated': len(resources) > 10,
            }
        )

    labels = dict(sorted((namespace.labels or {}).items()))
    annotations = dict(sorted((namespace.annotations or {}).items()))

    if namespace.default_service_account_present is True:
        default_service_account = 'Present'
    elif namespace.default_service_account_present is False:
        default_service_account = 'Missing'
    else:
        default_service_account = 'Not reported'

    return {
        'id': namespace.id,
        'cluster_name': cluster_name,
        'namespace': namespace.namespace,
        'status': namespace.status or 'Unknown',
        'uid': namespace.uid or '-',
        'age': format_age(namespace.created_at),
        'created_at': namespace.created_at,
        'collected_at': namespace.collected_at,
        'labels': labels,
        'annotations': annotations,
        'object_counts': object_counts,
        'workload_breakdown': {
            'deployments': workload_counts.get('Deployment', 0),
            'statefulsets': workload_counts.get('StatefulSet', 0),
            'daemonsets': workload_counts.get('DaemonSet', 0),
            'jobs': workload_counts.get('Job', 0),
            'cronjobs': workload_counts.get('CronJob', 0),
        },
        'quotas': quotas,
        'quota_count': len(quotas),
        'limit_range_count': namespace.limit_range_count,
        'network_policy_count': namespace.network_policy_count,
        'service_account_count': namespace.service_account_count,
        'default_service_account': default_service_account,
        'pod_security_enforce': labels.get(
            'pod-security.kubernetes.io/enforce',
            'Not configured',
        ),
        'pod_security_audit': labels.get(
            'pod-security.kubernetes.io/audit',
            'Not configured',
        ),
        'pod_security_warn': labels.get(
            'pod-security.kubernetes.io/warn',
            'Not configured',
        ),
    }
