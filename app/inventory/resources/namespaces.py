from __future__ import annotations

from typing import Any

from sqlalchemy import func, literal, tuple_, union_all

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


def _normalise_namespace_status(status: str | None) -> tuple[str, str]:
    value = (status or 'Unknown').strip()
    key = value.lower()
    if key == 'active':
        return 'Active', 'normal'
    if key == 'terminating':
        return 'Terminating', 'info'
    return value or 'Unknown', 'unknown'


def _configured_label(count: int | None, *, inherited_when_zero: bool = False) -> str:
    if count is None:
        return 'Not Reported'
    if count > 0:
        return f'Configured · {count}'
    return 'Inherited' if inherited_when_zero else 'Not Configured'


def get_namespace_filter_statuses(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(NamespaceInventory.status)
    query = filter_current_generation(query, NamespaceInventory)
    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(NamespaceInventory.status).all()
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
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
    query = filter_current_generation(query, NamespaceInventory)

    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)
    if status:
        query = query.filter(NamespaceInventory.status == status)
    if search:
        query = query.filter(NamespaceInventory.namespace.ilike(f'%{search}%'))

    summary_query = query.order_by(None)
    summary_rows = summary_query.with_entities(
        NamespaceInventory.status,
        NamespaceInventory.limit_range_count,
        NamespaceInventory.network_policy_count,
        NamespaceInventory.default_service_account_present,
        NamespaceInventory.labels,
    ).all()

    status_counts: dict[str, int] = {}
    active_namespaces = 0
    terminating_namespaces = 0
    unknown_namespaces = 0
    limit_range_configured = 0
    network_policy_configured = 0
    psa_enforce_configured = 0
    missing_default_service_accounts = 0

    for row in summary_rows:
        display_status, _ = _normalise_namespace_status(row.status)
        status_counts[display_status] = status_counts.get(display_status, 0) + 1
        if display_status == 'Active':
            active_namespaces += 1
        elif display_status == 'Terminating':
            terminating_namespaces += 1
        else:
            unknown_namespaces += 1

        if (row.limit_range_count or 0) > 0:
            limit_range_configured += 1
        if (row.network_policy_count or 0) > 0:
            network_policy_configured += 1
        if (row.labels or {}).get('pod-security.kubernetes.io/enforce'):
            psa_enforce_configured += 1
        if row.default_service_account_present is False:
            missing_default_service_accounts += 1

    cluster_rows = summary_query.with_entities(Cluster.name).distinct().all()
    total_clusters = len(cluster_rows)
    scope_label = cluster_rows[0][0] if cluster_id and cluster_rows else 'All Clusters'

    namespace_scope = summary_query.with_entities(
        NamespaceInventory.cluster_id.label('cluster_id'),
        NamespaceInventory.namespace.label('namespace'),
    ).subquery()
    quota_namespaces = db.session.query(
        ResourceQuotaInventory.cluster_id,
        ResourceQuotaInventory.namespace,
    )
    quota_namespaces = filter_current_generation(quota_namespaces, ResourceQuotaInventory)
    quota_namespaces = quota_namespaces.join(
        namespace_scope,
        (namespace_scope.c.cluster_id == ResourceQuotaInventory.cluster_id)
        & (namespace_scope.c.namespace == ResourceQuotaInventory.namespace),
    ).group_by(ResourceQuotaInventory.cluster_id, ResourceQuotaInventory.namespace).subquery()
    quota_configured = db.session.query(func.count()).select_from(quota_namespaces).scalar() or 0

    namespace_records, pagination = paginate_query(
        query.order_by(Cluster.name, NamespaceInventory.namespace),
        page=page,
        per_page=per_page,
    )
    namespace_keys = [(row.cluster_id, row.namespace) for row, _, _ in namespace_records]

    def _namespace_count_map(model) -> dict[tuple[str, str], int]:
        if not namespace_keys:
            return {}
        count_query = db.session.query(model.cluster_id, model.namespace, func.count(model.id))
        count_query = filter_current_generation(count_query, model)
        count_query = count_query.filter(tuple_(model.cluster_id, model.namespace).in_(namespace_keys))
        return {
            (row_cluster_id, row_namespace): count
            for row_cluster_id, row_namespace, count in count_query.group_by(
                model.cluster_id,
                model.namespace,
            ).all()
        }

    quota_counts = _namespace_count_map(ResourceQuotaInventory)
    inventory_rows: list[dict[str, Any]] = []
    for namespace, cluster_name, cluster_environment in namespace_records:
        lifecycle_label, lifecycle_tone = _normalise_namespace_status(namespace.status)
        key = (namespace.cluster_id, namespace.namespace)
        labels = namespace.labels or {}
        quota_count = quota_counts.get(key, 0)
        inventory_rows.append(
            {
                'id': namespace.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': namespace.namespace,
                'age': format_age(namespace.created_at),
                'lifecycle_label': lifecycle_label,
                'lifecycle_tone': lifecycle_tone,
                'quota_count': quota_count,
                'quota_display': _configured_label(quota_count),
                'limit_range_count': namespace.limit_range_count,
                'limit_range_display': _configured_label(namespace.limit_range_count),
                'network_policy_count': namespace.network_policy_count,
                'network_policy_display': _configured_label(namespace.network_policy_count),
                'pod_security_enforce': labels.get('pod-security.kubernetes.io/enforce'),
                'pod_security_enforce_display': (
                    labels.get('pod-security.kubernetes.io/enforce', '').title() or 'Inherited'
                ),
            }
        )

    total_namespaces = pagination['total_items']
    lifecycle_exceptions = terminating_namespaces + unknown_namespaces
    if total_namespaces == 0:
        lifecycle_label, lifecycle_tone = 'No Data', 'unknown'
    elif unknown_namespaces > 0:
        lifecycle_label, lifecycle_tone = 'Review Required', 'warning'
    elif terminating_namespaces > 0:
        lifecycle_label, lifecycle_tone = 'Transitioning', 'info'
    else:
        lifecycle_label, lifecycle_tone = 'Healthy', 'normal'

    return {
        'total_namespaces': total_namespaces,
        'total_clusters': total_clusters,
        'scope_label': scope_label,
        'active_namespaces': active_namespaces,
        'terminating_namespaces': terminating_namespaces,
        'unknown_namespaces': unknown_namespaces,
        'lifecycle_exceptions': lifecycle_exceptions,
        'lifecycle_label': lifecycle_label,
        'lifecycle_tone': lifecycle_tone,
        'status_counts': status_counts,
        'quota_configured_namespaces': quota_configured,
        'limit_range_configured_namespaces': limit_range_configured,
        'network_policy_configured_namespaces': network_policy_configured,
        'psa_enforce_configured_namespaces': psa_enforce_configured,
        'missing_default_service_accounts': missing_default_service_accounts,
        'namespaces': inventory_rows,
        'pagination': pagination,
    }


def get_namespace_detail(namespace_id: int) -> dict[str, Any] | None:
    query = db.session.query(
        NamespaceInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
    query = filter_current_generation(query, NamespaceInventory)
    result = query.filter(NamespaceInventory.id == namespace_id).first()
    if result is None:
        return None

    namespace, cluster_name, cluster_environment = result
    namespace_scope = {
        'cluster_id': namespace.cluster_id,
        'namespace': namespace.namespace,
    }

    workload_query = db.session.query(
        WorkloadInventory.workload_type,
        func.count(WorkloadInventory.id),
    )
    workload_query = filter_current_generation(workload_query, WorkloadInventory)
    workload_counts = {
        workload_type or 'Unknown': count
        for workload_type, count in workload_query.filter_by(**namespace_scope).group_by(
            WorkloadInventory.workload_type
        ).all()
    }
    total_workloads = sum(workload_counts.values())

    def _count_select(model, key: str, *filters: Any):
        count_query = db.session.query(literal(key).label('key'), func.count(model.id).label('count'))
        count_query = filter_current_generation(count_query, model)
        count_query = count_query.filter(
            model.cluster_id == namespace.cluster_id,
            model.namespace == namespace.namespace,
            *filters,
        )
        return count_query.statement

    aggregate = union_all(
        _count_select(PodInventory, 'pods'),
        _count_select(ServiceInventory, 'services'),
        _count_select(IngressInventory, 'ingresses'),
        _count_select(
            StorageInventory,
            'persistent_volume_claims',
            StorageInventory.storage_type == 'PersistentVolumeClaim',
        ),
        _count_select(
            ConfigurationInventory,
            'config_maps',
            ConfigurationInventory.object_type == 'ConfigMap',
        ),
        _count_select(
            ConfigurationInventory,
            'secrets',
            ConfigurationInventory.object_type == 'Secret',
        ),
    ).subquery()
    object_counts = {
        row._mapping['key']: row._mapping['count']
        for row in db.session.query(aggregate.c.key, aggregate.c.count).all()
    }
    object_counts['workloads'] = total_workloads

    quota_rows = (
        filter_current_generation(ResourceQuotaInventory.query, ResourceQuotaInventory)
        .filter_by(**namespace_scope)
        .order_by(ResourceQuotaInventory.name)
        .all()
    )
    quotas: list[dict[str, Any]] = []
    for quota in quota_rows:
        resources = [
            {
                'name': resource_name,
                'hard': format_quota_value(resource_name, (quota.hard or {}).get(resource_name)),
            }
            for resource_name in sorted((quota.hard or {}).keys())
        ]
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
        default_service_account = 'Not Reported'

    object_counts['resource_quotas'] = len(quotas)
    object_counts['tracked_total'] = total_workloads + sum(
        object_counts.get(key, 0)
        for key in (
            'pods',
            'services',
            'ingresses',
            'persistent_volume_claims',
            'config_maps',
            'secrets',
        )
    )

    lifecycle_label, lifecycle_tone = _normalise_namespace_status(namespace.status)
    psa_enforce = labels.get('pod-security.kubernetes.io/enforce')
    psa_audit = labels.get('pod-security.kubernetes.io/audit')
    psa_warn = labels.get('pod-security.kubernetes.io/warn')
    reported_controls = 1
    reported_controls += 1 if namespace.limit_range_count is not None else 0
    reported_controls += 1 if namespace.network_policy_count is not None else 0
    reported_controls += 1

    if lifecycle_label == 'Terminating':
        operational_context = {
            'title': 'Review Namespace Lifecycle',
            'description': (
                'Confirm that dependent workloads, finalizers, and retained resources '
                'are completing the intended deletion process.'
            ),
            'tone': 'info',
            'icon': 'hourglass',
        }
    elif lifecycle_tone == 'unknown':
        operational_context = {
            'title': 'Validate Namespace Lifecycle',
            'description': (
                'Refresh inventory and confirm the namespace state before making '
                'placement or policy decisions.'
            ),
            'tone': 'warning',
            'icon': 'circle-help',
        }
    elif default_service_account == 'Missing':
        operational_context = {
            'title': 'Restore Namespace Access Baseline',
            'description': (
                'Confirm why the default ServiceAccount is absent and whether '
                'workload identity behavior is affected.'
            ),
            'tone': 'warning',
            'icon': 'user-round-x',
        }
    else:
        operational_context = {
            'title': 'Namespace Snapshot Ready for Review',
            'description': (
                'No exceptional lifecycle or access signal is present in the current '
                'committed inventory snapshot.'
            ),
            'tone': 'normal',
            'icon': 'circle-check',
        }

    return {
        'id': namespace.id,
        'cluster_name': cluster_name,
        'cluster_environment': cluster_environment,
        'namespace': namespace.namespace,
        'status': namespace.status or 'Unknown',
        'lifecycle_label': lifecycle_label,
        'lifecycle_tone': lifecycle_tone,
        'uid': namespace.uid or 'Not Reported',
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
        'quota_display': _configured_label(len(quotas)),
        'limit_range_count': namespace.limit_range_count,
        'limit_range_display': _configured_label(namespace.limit_range_count),
        'network_policy_count': namespace.network_policy_count,
        'network_policy_display': _configured_label(namespace.network_policy_count),
        'service_account_count': namespace.service_account_count,
        'default_service_account': default_service_account,
        'pod_security_enforce': psa_enforce,
        'pod_security_audit': psa_audit,
        'pod_security_warn': psa_warn,
        'pod_security_enforce_display': psa_enforce.title() if psa_enforce else 'Inherited',
        'pod_security_audit_display': psa_audit.title() if psa_audit else 'Inherited',
        'pod_security_warn_display': psa_warn.title() if psa_warn else 'Inherited',
        'control_evidence_display': f'{reported_controls}/4 Reported',
        'operational_context': operational_context,
    }
