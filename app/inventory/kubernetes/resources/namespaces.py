from __future__ import annotations

from typing import Any, cast

from sqlalchemy import (
    Select,
    func,
    literal,
    or_,
    tuple_,
    union_all,
)

from app.common.inventory_generation import filter_current_generation
from app.common.pagination import paginate_query
from app.extensions.db import db
from app.inventory.kubernetes.formatting import format_quota_value
from app.inventory.kubernetes.resources.common import format_age
from app.models import (
    Cluster,
    ClusterInventory,
    ConfigurationInventory,
    IngressInventory,
    NamespaceInventory,
    PodInventory,
    ResourceQuotaInventory,
    ServiceInventory,
    StorageInventory,
    WorkloadInventory,
)

RESOURCE_QUOTA_EVIDENCE_KEY = 'inventory.resourcequotas'
CONFIGMAP_EVIDENCE_KEY = 'inventory.configmaps'
SECRET_EVIDENCE_KEY = 'inventory.secrets'
COLLECTED = 'Collected'


def _normalise_namespace_status(status: str | None) -> tuple[str, str]:
    value = (status or 'Unknown').strip()
    key = value.lower()
    if key == 'active':
        return 'Active', 'normal'
    if key == 'terminating':
        return 'Terminating', 'info'
    return value or 'Unknown', 'unknown'


def _configured_label(count: int | None) -> str:
    if count is None:
        return 'Not Reported'
    if count > 0:
        return f'Configured · {count}'
    return 'Not Configured'


def _psa_label(value: str | None) -> str:
    normalized = (value or '').strip()
    return normalized.title() if normalized else 'Not Explicitly Set'


def _resource_quota_collection_state(evidence: dict[str, Any] | None) -> str:
    state = (evidence or {}).get(RESOURCE_QUOTA_EVIDENCE_KEY)
    if state:
        return str(state)

    return 'Not Reported'


def _base_namespace_query():
    query = db.session.query(
        NamespaceInventory,
        Cluster.name.label('cluster_name'),
        Cluster.environment.label('cluster_environment'),
    ).join(Cluster, Cluster.id == NamespaceInventory.cluster_id)
    return filter_current_generation(query, NamespaceInventory)


def _apply_namespace_filters(query, *, cluster_id: str | None, status: str | None, search: str | None):
    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)
    if status == 'Unknown':
        query = query.filter(
            or_(
                NamespaceInventory.status.is_(None),
                func.trim(NamespaceInventory.status) == '',
            )
        )
    elif status:
        query = query.filter(func.lower(func.trim(NamespaceInventory.status)) == status.lower())
    if search:
        query = query.filter(NamespaceInventory.namespace.ilike(f'%{search}%'))
    return query


def _load_quota_collection_states(cluster_ids: set[str]) -> dict[str, str]:
    if not cluster_ids:
        return {}
    rows = (
        db.session.query(
            ClusterInventory.cluster_id,
            ClusterInventory.collection_evidence,
        )
        .filter(ClusterInventory.cluster_id.in_(cluster_ids))
        .all()
    )
    return {
        cluster_id: _resource_quota_collection_state(collection_evidence) for cluster_id, collection_evidence in rows
    }


def _summarize_namespace_rows(rows, quota_states: dict[str, str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        'status_counts': {},
        'active_namespaces': 0,
        'terminating_namespaces': 0,
        'unknown_namespaces': 0,
        'limit_range_configured_namespaces': 0,
        'network_policy_configured_namespaces': 0,
        'psa_enforce_configured_namespaces': 0,
        'missing_default_service_accounts': 0,
        'default_service_account_not_reported': 0,
        'quota_reported_namespaces': 0,
        'limit_range_reported_namespaces': 0,
        'network_policy_reported_namespaces': 0,
    }
    for row in rows:
        display_status, _ = _normalise_namespace_status(row.status)
        counts = summary['status_counts']
        counts[display_status] = counts.get(display_status, 0) + 1
        if display_status == 'Active':
            summary['active_namespaces'] += 1
        elif display_status == 'Terminating':
            summary['terminating_namespaces'] += 1
        else:
            summary['unknown_namespaces'] += 1

        summary['limit_range_configured_namespaces'] += int((row.limit_range_count or 0) > 0)
        summary['network_policy_configured_namespaces'] += int((row.network_policy_count or 0) > 0)
        summary['limit_range_reported_namespaces'] += int(row.limit_range_count is not None)
        summary['network_policy_reported_namespaces'] += int(row.network_policy_count is not None)
        summary['psa_enforce_configured_namespaces'] += int(
            bool((row.labels or {}).get('pod-security.kubernetes.io/enforce'))
        )
        summary['quota_reported_namespaces'] += int(quota_states.get(row.cluster_id) == COLLECTED)
        summary['missing_default_service_accounts'] += int(row.default_service_account_present is False)
        summary['default_service_account_not_reported'] += int(row.default_service_account_present is None)
    return summary


def _namespace_scope_label(cluster_id: str | None) -> str:
    if not cluster_id:
        return 'All Clusters'
    return db.session.query(Cluster.name).filter(Cluster.id == cluster_id).scalar() or 'Selected Cluster'


def _quota_configured_count(summary_query) -> int:
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
    )
    grouped = quota_namespaces.group_by(
        ResourceQuotaInventory.cluster_id,
        ResourceQuotaInventory.namespace,
    ).subquery()
    return db.session.query(func.count()).select_from(grouped).scalar() or 0


def _namespace_count_map(model, namespace_keys: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    if not namespace_keys:
        return {}
    query = db.session.query(model.cluster_id, model.namespace, func.count(model.id))
    query = filter_current_generation(query, model)
    query = query.filter(tuple_(model.cluster_id, model.namespace).in_(namespace_keys))
    return {
        (cluster_id, namespace): count
        for cluster_id, namespace, count in query.group_by(
            model.cluster_id,
            model.namespace,
        ).all()
    }


def _present_namespace_rows(records, quota_states: dict[str, str]) -> list[dict[str, Any]]:
    keys = [(item.cluster_id, item.namespace) for item, _, _ in records]
    quota_counts = _namespace_count_map(ResourceQuotaInventory, keys)
    result: list[dict[str, Any]] = []
    for namespace, cluster_name, cluster_environment in records:
        lifecycle_label, lifecycle_tone = _normalise_namespace_status(namespace.status)
        key = (namespace.cluster_id, namespace.namespace)
        quota_state = quota_states.get(namespace.cluster_id, 'Not Reported')
        quota_count = quota_counts.get(key, 0) if quota_state == COLLECTED else None
        labels = namespace.labels or {}
        result.append(
            {
                'id': namespace.id,
                'cluster_name': cluster_name,
                'cluster_environment': cluster_environment,
                'namespace': namespace.namespace,
                'lifecycle_label': lifecycle_label,
                'lifecycle_tone': lifecycle_tone,
                'quota_count': quota_count,
                'quota_display': _configured_label(quota_count),
                'limit_range_count': namespace.limit_range_count,
                'limit_range_display': _configured_label(namespace.limit_range_count),
                'network_policy_count': namespace.network_policy_count,
                'network_policy_display': _configured_label(namespace.network_policy_count),
                'pod_security_enforce': labels.get('pod-security.kubernetes.io/enforce'),
                'pod_security_enforce_display': _psa_label(labels.get('pod-security.kubernetes.io/enforce')),
            }
        )
    return result


def _lifecycle_posture(total: int, terminating: int, unknown: int) -> tuple[str, str]:
    if total == 0:
        return 'No Data', 'unknown'
    if unknown > 0:
        return 'Review Required', 'warning'
    if terminating > 0:
        return 'Transitioning', 'info'
    return 'Healthy', 'normal'


def get_namespace_filter_statuses(cluster_id: str | None = None) -> list[str]:
    query = db.session.query(NamespaceInventory.status)
    query = filter_current_generation(query, NamespaceInventory)
    if cluster_id:
        query = query.filter(NamespaceInventory.cluster_id == cluster_id)
    rows = query.distinct().order_by(NamespaceInventory.status).all()
    statuses = {_normalise_namespace_status(row[0])[0] for row in rows}
    priority = {'Active': 0, 'Terminating': 1, 'Unknown': 2}
    return sorted(statuses, key=lambda value: (priority.get(value, 3), value.lower()))


def get_namespace_inventory(
    cluster_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    query = _apply_namespace_filters(
        _base_namespace_query(),
        cluster_id=cluster_id,
        status=status,
        search=search,
    )
    summary_query = query.order_by(None)
    summary_rows = summary_query.with_entities(
        NamespaceInventory.cluster_id,
        NamespaceInventory.status,
        NamespaceInventory.limit_range_count,
        NamespaceInventory.network_policy_count,
        NamespaceInventory.default_service_account_present,
        NamespaceInventory.labels,
    ).all()
    quota_states = _load_quota_collection_states({row.cluster_id for row in summary_rows})
    summary = _summarize_namespace_rows(summary_rows, quota_states)

    records, pagination = paginate_query(
        query.order_by(Cluster.name, NamespaceInventory.namespace),
        page=page,
        per_page=per_page,
    )
    total_namespaces = pagination['total_items']
    lifecycle_label, lifecycle_tone = _lifecycle_posture(
        total_namespaces,
        summary['terminating_namespaces'],
        summary['unknown_namespaces'],
    )
    summary.update(
        {
            'total_namespaces': total_namespaces,
            'total_clusters': len(summary_query.with_entities(Cluster.name).distinct().all()),
            'scope_label': _namespace_scope_label(cluster_id),
            'lifecycle_exceptions': (summary['terminating_namespaces'] + summary['unknown_namespaces']),
            'lifecycle_label': lifecycle_label,
            'lifecycle_tone': lifecycle_tone,
            'quota_configured_namespaces': _quota_configured_count(summary_query),
            'namespaces': _present_namespace_rows(records, quota_states),
            'pagination': pagination,
        }
    )
    return summary


def _namespace_workload_counts(namespace: NamespaceInventory) -> dict[str, int]:
    query = db.session.query(
        WorkloadInventory.workload_type,
        func.count(WorkloadInventory.id),
    )
    query = filter_current_generation(query, WorkloadInventory)
    rows = query.filter_by(
        cluster_id=namespace.cluster_id,
        namespace=namespace.namespace,
    ).group_by(WorkloadInventory.workload_type)
    return {workload_type or 'Unknown': count for workload_type, count in rows.all()}


def _count_select(model, namespace: NamespaceInventory, key: str, *filters: Any):
    query = db.session.query(literal(key).label('key'), func.count(model.id).label('count'))
    query = filter_current_generation(query, model)
    statement = query.filter(
        model.cluster_id == namespace.cluster_id,
        model.namespace == namespace.namespace,
        *filters,
    ).statement
    return cast(Select[Any], statement)


def _namespace_object_counts(
    namespace: NamespaceInventory,
    total_workloads: int,
    collection_evidence: dict[str, Any],
) -> dict[str, Any]:
    aggregate = union_all(
        _count_select(PodInventory, namespace, 'pods'),
        _count_select(ServiceInventory, namespace, 'services'),
        _count_select(IngressInventory, namespace, 'ingresses'),
        _count_select(
            StorageInventory,
            namespace,
            'persistent_volume_claims',
            StorageInventory.storage_type == 'PersistentVolumeClaim',
        ),
        _count_select(
            ConfigurationInventory,
            namespace,
            'config_maps',
            ConfigurationInventory.object_type == 'ConfigMap',
        ),
        _count_select(
            ConfigurationInventory,
            namespace,
            'secrets',
            ConfigurationInventory.object_type == 'Secret',
        ),
    ).subquery()
    result = {
        row._mapping['key']: row._mapping['count'] for row in db.session.query(aggregate.c.key, aggregate.c.count).all()
    }
    result['workloads'] = total_workloads
    evidence_by_key = {
        'config_maps': str(collection_evidence.get(CONFIGMAP_EVIDENCE_KEY) or 'Not Reported'),
        'secrets': str(collection_evidence.get(SECRET_EVIDENCE_KEY) or 'Not Reported'),
    }
    for key, state in evidence_by_key.items():
        if state != COLLECTED:
            result[key] = None
    result['reported_types'] = 5 + sum(state == COLLECTED for state in evidence_by_key.values())
    result['total_types'] = 7
    result['evidence_display'] = f'{result["reported_types"]}/7 Reported'
    result['missing_evidence'] = [
        label
        for key, label in (('config_maps', 'ConfigMap'), ('secrets', 'Secret'))
        if evidence_by_key[key] != COLLECTED
    ]
    result['tracked_total'] = total_workloads + sum(
        result.get(key) or 0
        for key in (
            'pods',
            'services',
            'ingresses',
            'persistent_volume_claims',
            'config_maps',
            'secrets',
        )
    )
    return result


def _namespace_quotas(namespace: NamespaceInventory) -> tuple[list[dict[str, Any]], str]:
    rows = (
        filter_current_generation(ResourceQuotaInventory.query, ResourceQuotaInventory)
        .filter_by(cluster_id=namespace.cluster_id, namespace=namespace.namespace)
        .order_by(ResourceQuotaInventory.name)
        .all()
    )
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=namespace.cluster_id).first()
    collection_state = (
        _resource_quota_collection_state(cluster_inventory.collection_evidence) if cluster_inventory else 'Not Reported'
    )
    quotas = []
    for quota in rows:
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
    return quotas, collection_state


def _default_service_account_label(namespace: NamespaceInventory) -> str:
    if namespace.default_service_account_present is True:
        return 'Present'
    if namespace.default_service_account_present is False:
        return 'Missing'
    return 'Not Reported'


def _control_evidence(
    namespace: NamespaceInventory,
    quota_collection_state: str,
) -> tuple[int, list[str]]:
    reported = int(quota_collection_state == COLLECTED)
    reported += int(namespace.limit_range_count is not None)
    reported += int(namespace.network_policy_count is not None)
    reported += 1  # Namespace labels were collected with the Namespace object.
    reported += int(
        namespace.service_account_count is not None and namespace.default_service_account_present is not None
    )

    missing = []
    if quota_collection_state != COLLECTED:
        missing.append('ResourceQuota')
    if namespace.limit_range_count is None:
        missing.append('LimitRange')
    if namespace.network_policy_count is None:
        missing.append('NetworkPolicy')
    if namespace.service_account_count is None or namespace.default_service_account_present is None:
        missing.append('ServiceAccount')
    return reported, missing


def _namespace_operational_context(
    lifecycle_label: str,
    lifecycle_tone: str,
    default_service_account: str,
    missing_evidence: list[str],
) -> dict[str, str]:
    if lifecycle_label == 'Terminating':
        return {
            'title': 'Review Namespace Lifecycle',
            'description': (
                'Confirm that dependent workloads, finalizers, and retained resources '
                'are completing the intended deletion process.'
            ),
            'tone': 'info',
            'icon': 'hourglass',
        }
    if lifecycle_tone == 'unknown':
        return {
            'title': 'Validate Namespace Lifecycle',
            'description': (
                'Refresh inventory and confirm the namespace state before making placement or policy decisions.'
            ),
            'tone': 'warning',
            'icon': 'circle-help',
        }
    if missing_evidence:
        return {
            'title': 'Validate Namespace Control Evidence',
            'description': (
                'Refresh inventory permissions and collection for '
                f'{", ".join(missing_evidence)} before making governance or access decisions.'
            ),
            'tone': 'warning',
            'icon': 'shield-question',
        }
    if default_service_account == 'Missing':
        return {
            'title': 'Restore Namespace Access Baseline',
            'description': (
                'Confirm why the default ServiceAccount is absent and whether workload identity behavior is affected.'
            ),
            'tone': 'warning',
            'icon': 'user-round-x',
        }
    return {
        'title': 'Namespace Snapshot Ready for Review',
        'description': (
            'No exceptional lifecycle or access signal is present in the current committed inventory snapshot.'
        ),
        'tone': 'normal',
        'icon': 'circle-check',
    }


def get_namespace_detail(namespace_id: int) -> dict[str, Any] | None:
    query = _base_namespace_query()
    result = query.filter(NamespaceInventory.id == namespace_id).first()
    if result is None:
        return None

    namespace, cluster_name, cluster_environment = result
    workload_counts = _namespace_workload_counts(namespace)
    total_workloads = sum(workload_counts.values())
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=namespace.cluster_id).first()
    collection_evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    object_counts = _namespace_object_counts(
        namespace,
        total_workloads,
        collection_evidence,
    )
    quotas, quota_collection_state = _namespace_quotas(namespace)
    object_counts['resource_quotas'] = len(quotas)

    labels = dict(sorted((namespace.labels or {}).items()))
    annotations = dict(sorted((namespace.annotations or {}).items()))
    default_service_account = _default_service_account_label(namespace)
    lifecycle_label, lifecycle_tone = _normalise_namespace_status(namespace.status)
    reported_controls, missing_evidence = _control_evidence(
        namespace,
        quota_collection_state,
    )
    psa_enforce = labels.get('pod-security.kubernetes.io/enforce')
    psa_audit = labels.get('pod-security.kubernetes.io/audit')
    psa_warn = labels.get('pod-security.kubernetes.io/warn')

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
        'quota_count': len(quotas) if quota_collection_state == COLLECTED else None,
        'quota_display': _configured_label(len(quotas) if quota_collection_state == COLLECTED else None),
        'quota_collection_state': quota_collection_state,
        'limit_range_count': namespace.limit_range_count,
        'limit_range_display': _configured_label(namespace.limit_range_count),
        'network_policy_count': namespace.network_policy_count,
        'network_policy_display': _configured_label(namespace.network_policy_count),
        'service_account_count': namespace.service_account_count,
        'default_service_account': default_service_account,
        'pod_security_enforce': psa_enforce,
        'pod_security_audit': psa_audit,
        'pod_security_warn': psa_warn,
        'pod_security_enforce_display': _psa_label(psa_enforce),
        'pod_security_audit_display': _psa_label(psa_audit),
        'pod_security_warn_display': _psa_label(psa_warn),
        'control_evidence_display': f'{reported_controls}/5 Reported',
        'missing_evidence': missing_evidence,
        'operational_context': _namespace_operational_context(
            lifecycle_label,
            lifecycle_tone,
            default_service_account,
            missing_evidence,
        ),
    }
