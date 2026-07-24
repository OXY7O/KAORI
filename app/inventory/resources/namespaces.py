from __future__ import annotations

from typing import Any

from sqlalchemy import func, tuple_

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.formatting import format_quota_value
from app.inventory.resources.common import format_age
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
    query = filter_current_generation(query, NamespaceInventory)

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
    page: int = 1,
    per_page: int = 5,
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

    summary_query = query.order_by(None)
    status_rows = (
        summary_query.with_entities(
            NamespaceInventory.status,
            func.count(NamespaceInventory.id),
        )
        .group_by(NamespaceInventory.status)
        .all()
    )
    cluster_count = (
        summary_query.with_entities(
            func.count(func.distinct(NamespaceInventory.cluster_id)),
        )
        .scalar()
        or 0
    )
    namespace_records, pagination = paginate_query(
        query.order_by(
            Cluster.name,
            NamespaceInventory.namespace,
        ),
        page=page,
        per_page=per_page,
    )
    namespace_keys = [(row.cluster_id, row.namespace) for row, _ in namespace_records]

    def _namespace_count_map(model) -> dict[tuple[str, str], int]:
        if not namespace_keys:
            return {}

        count_query = db.session.query(
            model.cluster_id,
            model.namespace,
            func.count(model.id),
        )
        count_query = filter_current_generation(count_query, model)

        count_query = count_query.filter(tuple_(model.cluster_id, model.namespace).in_(namespace_keys))

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

    status_counts = {
        (namespace_status or 'Unknown'): count
        for namespace_status, count in status_rows
    }

    inventory_rows: list[dict[str, Any]] = []
    for namespace, cluster_name in namespace_records:
        namespace_status = namespace.status or 'Unknown'
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
                'pod_security_enforce': (namespace.labels or {}).get('pod-security.kubernetes.io/enforce'),
                'pod_security_audit': (namespace.labels or {}).get('pod-security.kubernetes.io/audit'),
                'pod_security_warn': (namespace.labels or {}).get('pod-security.kubernetes.io/warn'),
            }
        )

    return {
        'total_namespaces': pagination['total_items'],
        'total_clusters': cluster_count,
        'active_namespaces': status_counts.get('Active', 0),
        'status_counts': status_counts,
        'namespaces': inventory_rows,
        'pagination': pagination,
    }


def get_namespace_detail(
    namespace_id: int,
) -> dict[str, Any] | None:
    query = db.session.query(
        NamespaceInventory,
        Cluster.name.label('cluster_name'),
    ).join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
    query = filter_current_generation(query, NamespaceInventory)
    result = query.filter(NamespaceInventory.id == namespace_id).first()

    if result is None:
        return None

    namespace, cluster_name = result

    workload_count_query = db.session.query(
        WorkloadInventory.workload_type,
        func.count(WorkloadInventory.id),
    )
    workload_count_query = filter_current_generation(workload_count_query, WorkloadInventory)
    workload_counts = {
        workload_type or 'Unknown': count
        for workload_type, count in (
            workload_count_query
            .filter(
                WorkloadInventory.cluster_id == namespace.cluster_id,
                WorkloadInventory.namespace == namespace.namespace,
            )
            .group_by(WorkloadInventory.workload_type)
            .all()
        )
    }

    def _current_namespace_count(model, **filters: Any) -> int:
        query = filter_current_generation(model.query, model)
        return query.filter_by(**filters).count()

    namespace_scope = {
        'cluster_id': namespace.cluster_id,
        'namespace': namespace.namespace,
    }
    object_counts = {
        'workloads': _current_namespace_count(WorkloadInventory, **namespace_scope),
        'pods': _current_namespace_count(PodInventory, **namespace_scope),
        'services': _current_namespace_count(ServiceInventory, **namespace_scope),
        'ingresses': _current_namespace_count(IngressInventory, **namespace_scope),
        'persistent_volume_claims': _current_namespace_count(
            StorageInventory,
            **namespace_scope,
            storage_type='PersistentVolumeClaim',
        ),
        'config_maps': _current_namespace_count(
            ConfigurationInventory,
            **namespace_scope,
            object_type='ConfigMap',
        ),
        'secrets': _current_namespace_count(
            ConfigurationInventory,
            **namespace_scope,
            object_type='Secret',
        ),
        'resource_quotas': _current_namespace_count(ResourceQuotaInventory, **namespace_scope),
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
        filter_current_generation(ResourceQuotaInventory.query, ResourceQuotaInventory)
        .filter_by(
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
