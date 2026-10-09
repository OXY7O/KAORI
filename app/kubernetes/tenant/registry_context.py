from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import case, func, or_

from app.common.pagination import paginate_query
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.kubernetes.tenant.allocation_cutover import allocation_control_state, build_allocation_cutover_state
from app.kubernetes.tenant.capacity_governance import (
    build_capacity_governance_summaries,
    build_capacity_governance_summary,
)
from app.kubernetes.tenant.native_provider import tenant_workspace_connection_available
from app.kubernetes.tenant.resource_profile_controls import (
    _tenant_capability_statuses,
    evaluate_resource_profile_advanced_controls,
)
from app.kubernetes.tenant.service_contracts import (
    _ALLOWED_ENVIRONMENTS,
    _ALLOWED_PROFILE_CLASSES,
    RESOURCE_PROFILE_ADVANCED_CONTROLS,
    RESOURCE_PROFILE_PRESETS,
)
from app.models import AuditEvent, Cluster
from app.models.cluster import ClusterStatus
from app.models.kubernetes import KubernetesConnection
from app.models.tenant import (
    Tenant,
    TenantCapacityDecision,
    TenantEnvironment,
    TenantEnvironmentName,
    TenantLifecycleStatus,
    TenantNamespace,
    TenantNamespaceProvisioningStatus,
    TenantOwnershipStatus,
    TenantResourceProfile,
    TenantResourceProfileClass,
)


def get_ready_native_clusters() -> list[Cluster]:
    clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .filter(Cluster.status == ClusterStatus.CONNECTED.value)
        .order_by(Cluster.name.asc())
        .all()
    )
    return [cluster for cluster in clusters if tenant_workspace_connection_available(cluster.kubernetes_connection)]


def _ready_tenant_environment_options() -> list[TenantEnvironment]:
    return (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )


def get_tenant_shell_context() -> dict[str, Any]:
    """Return only page-shell Tenant state required by every Tenant route."""

    ready_clusters = get_ready_native_clusters()
    return {
        'ready_clusters': ready_clusters,
        'tenant_count': Tenant.query.filter(
            Tenant.lifecycle_status.notin_((TenantLifecycleStatus.DECOMMISSIONED.value, TenantLifecycleStatus.RELEASED.value))
        ).count(),
        'profile_count': TenantResourceProfile.query.count(),
        'namespace_count': TenantNamespace.query.filter(
            TenantNamespace.provisioning_status.notin_((TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value))
        ).count(),
        'ready_namespace_count': TenantNamespace.query.filter_by(
            provisioning_status=TenantNamespaceProvisioningStatus.READY.value
        ).count(),
        'native_available': bool(ready_clusters),
    }


def get_resource_profile_workspace_context() -> dict[str, Any]:
    """Return Resource Profiles-only capacity and profile summary context."""

    registered_clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .order_by(Cluster.name.asc(), Cluster.id.asc())
        .all()
    )
    capacity_by_cluster = build_capacity_governance_summaries([str(cluster.id) for cluster in registered_clusters])
    capacity_governance = [
        {'cluster': cluster, **capacity_by_cluster[str(cluster.id)]} for cluster in registered_clusters
    ]
    profile_count = TenantResourceProfile.query.count()
    return {
        'registered_clusters': registered_clusters,
        'capacity_governance': capacity_governance,
        'capacity_policy_state': {
            str(item['cluster'].id): item['policy'] for item in capacity_governance if item.get('policy') is not None
        },
        'resource_profile_stats': {
            'total': profile_count,
            'enabled': TenantResourceProfile.query.filter_by(enabled=True).count(),
            'custom': TenantResourceProfile.query.filter_by(
                profile_class=TenantResourceProfileClass.CUSTOM.value
            ).count(),
            'active_allocations': TenantNamespace.query.filter(
                TenantNamespace.provisioning_status.notin_(
                    (TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value)
                ),
                TenantNamespace.resource_profile_id.isnot(None),
            ).count(),
        },
        'resource_profile_advanced_controls': RESOURCE_PROFILE_ADVANCED_CONTROLS,
    }


def get_namespace_provisioning_support_context() -> dict[str, Any]:
    """Return form support state required only by Namespace Provisioning."""

    environment_options = _ready_tenant_environment_options()
    return {
        'environment_options': environment_options,
        'resource_profile_presets': RESOURCE_PROFILE_PRESETS,
        'resource_profile_advanced_controls': RESOURCE_PROFILE_ADVANCED_CONTROLS,
        'tenant_environment_advanced_control_state': {
            str(environment.id): {
                'tenant_id': environment.tenant_id,
                'provider_key': environment.tenant.provider_key,
                'provider_state': environment.tenant.provider_state,
                'controls': evaluate_resource_profile_advanced_controls(
                    {key: True for key in RESOURCE_PROFILE_ADVANCED_CONTROLS},
                    provider_key=environment.tenant.provider_key,
                    capability_statuses=_tenant_capability_statuses(environment.tenant),
                ),
            }
            for environment in environment_options
        },
    }


def _resource_profile_rollout_targets(profile_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not profile_ids:
        return {}

    rows = (
        db.session.query(
            TenantNamespace.resource_profile_id,
            Tenant.id,
            Tenant.name,
            Tenant.provider_key,
            func.count(TenantNamespace.id),
            func.sum(
                case(
                    (
                        or_(
                            TenantNamespace.resource_profile_version.is_(None),
                            TenantNamespace.resource_profile_version != TenantResourceProfile.version,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
        )
        .join(TenantEnvironment, TenantEnvironment.id == TenantNamespace.tenant_environment_id)
        .join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .join(TenantResourceProfile, TenantResourceProfile.id == TenantNamespace.resource_profile_id)
        .filter(
            TenantNamespace.resource_profile_id.in_(profile_ids),
            TenantNamespace.provisioning_status.notin_(
                    (TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value)
                ),
        )
        .group_by(
            TenantNamespace.resource_profile_id,
            Tenant.id,
            Tenant.name,
            Tenant.provider_key,
        )
        .order_by(Tenant.name.asc())
        .all()
    )

    result: dict[int, list[dict[str, Any]]] = {profile_id: [] for profile_id in profile_ids}
    for profile_id, tenant_id, tenant_name, provider_key, count, outdated in rows:
        if profile_id is None:
            continue
        result.setdefault(int(profile_id), []).append(
            {
                'tenant_id': str(tenant_id),
                'tenant_name': str(tenant_name),
                'provider_key': str(provider_key),
                'namespaces': int(count or 0),
                'outdated': int(outdated or 0),
            }
        )
    return result


_ALLOWED_PAGE_SIZES = (5, 10, 25, 50)


def _paged_context(query: Any, *, page: int, per_page: int) -> tuple[list[Any], dict[str, Any]]:
    normalized_page = max(int(page), 1)
    normalized_per_page = per_page if per_page in _ALLOWED_PAGE_SIZES else 5
    pagination = query.paginate(page=normalized_page, per_page=normalized_per_page, error_out=False)
    if pagination.pages and normalized_page > pagination.pages:
        normalized_page = pagination.pages
        pagination = query.paginate(page=normalized_page, per_page=normalized_per_page, error_out=False)

    start_item = ((normalized_page - 1) * normalized_per_page + 1) if pagination.total else 0
    end_item = min(normalized_page * normalized_per_page, pagination.total) if pagination.total else 0
    return list(pagination.items), {
        'page': normalized_page,
        'per_page': normalized_per_page,
        'total': pagination.total,
        'pages': max(pagination.pages, 1),
        'start_item': start_item,
        'end_item': end_item,
        'has_prev': pagination.has_prev,
        'prev_num': pagination.prev_num,
        'has_next': pagination.has_next,
        'next_num': pagination.next_num,
        'allowed_per_page': _ALLOWED_PAGE_SIZES,
    }


def get_tenant_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    cluster_id: str = '',
    environment: str = '',
    lifecycle_status: str = '',
    include_decommission_preflight: bool = True,
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_cluster_id = cluster_id.strip()
    normalized_environment = environment.strip().lower()
    normalized_lifecycle = lifecycle_status.strip().lower()

    query = Tenant.query

    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(Tenant.name).like(pattern),
                func.lower(Tenant.slug).like(pattern),
            )
        )
    if normalized_cluster_id:
        query = query.filter(Tenant.cluster_id == normalized_cluster_id)
    if normalized_lifecycle:
        query = query.filter(Tenant.lifecycle_status == normalized_lifecycle)
    if normalized_environment:
        query = (
            query.join(TenantEnvironment, TenantEnvironment.tenant_id == Tenant.id)
            .filter(TenantEnvironment.environment == normalized_environment)
            .distinct()
        )

    items, pagination = paginate_query(
        query.order_by(Tenant.created_at.desc(), Tenant.name.asc()),
        page=page,
        per_page=per_page,
    )

    tenant_ids = [item.id for item in items]
    environment_map: dict[str, list[str]] = {tenant_id: [] for tenant_id in tenant_ids}
    namespace_count_map: dict[str, int] = {tenant_id: 0 for tenant_id in tenant_ids}
    namespace_history_count_map: dict[str, int] = {tenant_id: 0 for tenant_id in tenant_ids}

    if tenant_ids:
        environment_rows: list[TenantEnvironment] = (
            TenantEnvironment.query.filter(TenantEnvironment.tenant_id.in_(tenant_ids))
            .order_by(TenantEnvironment.tenant_id.asc(), TenantEnvironment.environment.asc())
            .all()
        )
        for environment_row in environment_rows:
            environment_map.setdefault(environment_row.tenant_id, []).append(environment_row.environment)

        if include_decommission_preflight:
            namespace_history_rows = (
                db.session.query(TenantEnvironment.tenant_id, func.count(TenantNamespace.id))
                .join(TenantNamespace, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
                .filter(TenantEnvironment.tenant_id.in_(tenant_ids))
                .group_by(TenantEnvironment.tenant_id)
                .all()
            )
            namespace_history_count_map.update(
                {str(tenant_id): int(count) for tenant_id, count in namespace_history_rows}
            )

        namespace_rows = (
            db.session.query(TenantEnvironment.tenant_id, func.count(TenantNamespace.id))
            .join(TenantNamespace, TenantNamespace.tenant_environment_id == TenantEnvironment.id)
            .filter(
                TenantEnvironment.tenant_id.in_(tenant_ids),
                TenantNamespace.provisioning_status.notin_(
                    (TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value)
                ),
            )
            .group_by(TenantEnvironment.tenant_id)
            .all()
        )
        namespace_count_map.update({str(tenant_id): int(count) for tenant_id, count in namespace_rows})

    cluster_ids = {item.cluster_id for item in items}
    cluster_map = (
        {str(cluster.id): cluster for cluster in Cluster.query.filter(Cluster.id.in_(cluster_ids)).all()}
        if cluster_ids
        else {}
    )

    if include_decommission_preflight:
        from app.kubernetes.tenant.decommission_service import build_tenant_decommission_preflight

    release_evidence: dict[str, dict[str, Any]] = {}
    if tenant_ids and include_decommission_preflight:
        latest_ids = (
            db.session.query(func.max(AuditEvent.id).label('id'))
            .filter(
                AuditEvent.target_type == 'kubernetes_tenant_release_preflight',
                AuditEvent.target_id.in_(tenant_ids),
            )
            .group_by(AuditEvent.target_id)
            .subquery()
        )
        recent_rows = db.session.query(AuditEvent).join(
            latest_ids, AuditEvent.id == latest_ids.c.id
        ).all()
        release_evidence = {
            str(event.target_id): dict(event.metadata_json or {}) for event in recent_rows
        }

    handoff_plans: dict[str, dict[str, Any]] = {}
    handoff_approvals: dict[str, dict[str, Any]] = {}
    handoff_dry_runs: dict[str, dict[str, Any]] = {}
    if tenant_ids and include_decommission_preflight:
        for target_type, destination in (
            ('kubernetes_tenant_release_handoff_plan', handoff_plans),
            ('kubernetes_tenant_release_handoff_approval', handoff_approvals),
            ('kubernetes_tenant_release_native_handoff_dry_run', handoff_dry_runs),
        ):
            latest_ids = (
                db.session.query(func.max(AuditEvent.id).label('id'))
                .filter(
                    AuditEvent.target_type == target_type,
                    AuditEvent.target_id.in_(tenant_ids),
                )
                .group_by(AuditEvent.target_id)
                .subquery()
            )
            rows = db.session.query(AuditEvent).join(
                latest_ids, AuditEvent.id == latest_ids.c.id
            ).all()
            destination.update({
                str(event.target_id): dict(event.metadata_json or {})
                for event in rows
            })

    tenant_rows: list[dict[str, Any]] = []
    for item in items:
        row: dict[str, Any] = {
            'tenant': item,
            'cluster': cluster_map.get(str(item.cluster_id)),
            'environments': environment_map.get(item.id, []),
            'namespace_count': namespace_count_map.get(item.id, 0),
        }
        if include_decommission_preflight:
            row['namespace_history_count'] = namespace_history_count_map.get(item.id, 0)
            row['decommission_preflight'] = build_tenant_decommission_preflight(item.id)
            row['release_preflight'] = release_evidence.get(item.id)
            row['release_handoff_plan'] = handoff_plans.get(item.id)
            row['release_handoff_approval'] = handoff_approvals.get(item.id)
            row['release_native_handoff_dry_run'] = handoff_dry_runs.get(item.id)
        tenant_rows.append(row)

    return {
        'tenants': items,
        'tenant_rows': tenant_rows,
        'tenant_pagination': pagination,
        'tenant_registry_filters': {
            'search': normalized_search,
            'cluster_id': normalized_cluster_id,
            'environment': normalized_environment,
            'lifecycle_status': normalized_lifecycle,
        },
        'tenant_cluster_options': Cluster.query.order_by(Cluster.name.asc()).all(),
        'tenant_environment_filter_options': [item.value for item in TenantEnvironmentName],
        'tenant_lifecycle_filter_options': [item.value for item in TenantLifecycleStatus],
    }


def get_resource_profile_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    profile_class: str = '',
    state: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_class = profile_class.strip().lower()
    normalized_state = state.strip().lower()

    query = TenantResourceProfile.query
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantResourceProfile.name).like(pattern),
                func.lower(func.coalesce(TenantResourceProfile.description, '')).like(pattern),
            )
        )
    if normalized_class in _ALLOWED_PROFILE_CLASSES:
        query = query.filter(TenantResourceProfile.profile_class == normalized_class)
    else:
        normalized_class = ''
    if normalized_state == 'enabled':
        query = query.filter(TenantResourceProfile.enabled.is_(True))
    elif normalized_state == 'disabled':
        query = query.filter(TenantResourceProfile.enabled.is_(False))
    else:
        normalized_state = ''

    items, pagination = paginate_query(
        query.order_by(TenantResourceProfile.created_at.desc(), TenantResourceProfile.name.asc()),
        page=page,
        per_page=per_page,
    )

    profile_ids = [profile.id for profile in items]
    namespace_counts: dict[int, int] = {}
    capacity_decision_counts: dict[int, int] = {}
    if profile_ids:
        namespace_counts = {
            int(profile_id): int(count)
            for profile_id, count in (
                db.session.query(TenantNamespace.resource_profile_id, func.count(TenantNamespace.id))
                .filter(TenantNamespace.resource_profile_id.in_(profile_ids))
                .group_by(TenantNamespace.resource_profile_id)
                .all()
            )
            if profile_id is not None
        }
        capacity_decision_counts = {
            int(profile_id): int(count)
            for profile_id, count in (
                db.session.query(TenantCapacityDecision.resource_profile_id, func.count(TenantCapacityDecision.id))
                .filter(TenantCapacityDecision.resource_profile_id.in_(profile_ids))
                .group_by(TenantCapacityDecision.resource_profile_id)
                .all()
            )
            if profile_id is not None
        }

    profile_dependencies = {
        profile.id: {
            'namespaces': namespace_counts.get(profile.id, 0),
            'capacity_decisions': capacity_decision_counts.get(profile.id, 0),
            'total': namespace_counts.get(profile.id, 0) + capacity_decision_counts.get(profile.id, 0),
        }
        for profile in items
    }
    profile_rollout_targets = _resource_profile_rollout_targets(profile_ids)

    return {
        'profiles': items,
        'profile_dependencies': profile_dependencies,
        'profile_rollout_targets': profile_rollout_targets,
        'resource_profile_presets': RESOURCE_PROFILE_PRESETS,
        'profile_pagination': pagination,
        'profile_registry_filters': {
            'search': normalized_search,
            'profile_class': normalized_class,
            'state': normalized_state,
        },
        'profile_class_filter_options': [item.value for item in TenantResourceProfileClass],
    }


def get_capacity_decision_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    decision: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip()
    normalized_decision = decision.strip().lower()

    query = (
        db.session.query(TenantCapacityDecision, Cluster, TenantResourceProfile)
        .join(
            Cluster,
            Cluster.id == TenantCapacityDecision.cluster_id,
        )
        .outerjoin(
            TenantResourceProfile,
            TenantResourceProfile.id == TenantCapacityDecision.resource_profile_id,
        )
    )
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantCapacityDecision.namespace).like(pattern),
                func.lower(Cluster.name).like(pattern),
                func.lower(Cluster.environment).like(pattern),
                func.lower(TenantCapacityDecision.operation).like(pattern),
                func.lower(TenantCapacityDecision.capacity_state).like(pattern),
                func.lower(TenantResourceProfile.name).like(pattern),
            )
        )

    if normalized_decision in {'allow', 'block'}:
        query = query.filter(TenantCapacityDecision.decision == normalized_decision)
    else:
        normalized_decision = ''

    items, pagination = paginate_query(
        query.order_by(TenantCapacityDecision.created_at.desc(), TenantCapacityDecision.id.desc()),
        page=page,
        per_page=per_page,
    )

    return {
        'capacity_decision_rows': [
            {
                'decision': decision_row,
                'cluster': cluster,
                'profile': profile,
                'created_at_label': present_user_datetime(decision_row.created_at, empty='—'),
                'data_cutoff_label': present_user_datetime(decision_row.data_cutoff, empty='No cutoff'),
            }
            for decision_row, cluster, profile in items
        ],
        'capacity_decision_pagination': pagination,
        'capacity_decision_filters': {
            'search': normalized_search,
            'decision': normalized_decision,
        },
    }


def _namespace_registry_query(
    *,
    search: str,
    tenant_id: str,
    environment: str,
    status: str,
):
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_environment = environment.strip().lower()
    normalized_status = status.strip().lower()
    allowed_statuses = {item.value for item in TenantNamespaceProvisioningStatus}

    query = TenantNamespace.query.join(
        TenantEnvironment,
        TenantNamespace.tenant_environment_id == TenantEnvironment.id,
    ).join(Tenant, TenantEnvironment.tenant_id == Tenant.id)
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantNamespace.namespace).like(pattern),
                func.lower(Tenant.name).like(pattern),
                func.lower(Tenant.slug).like(pattern),
            )
        )
    if normalized_tenant_id:
        query = query.filter(Tenant.id == normalized_tenant_id)
    if normalized_environment in _ALLOWED_ENVIRONMENTS:
        query = query.filter(TenantEnvironment.environment == normalized_environment)
    else:
        normalized_environment = ''
    if normalized_status in allowed_statuses:
        query = query.filter(TenantNamespace.provisioning_status == normalized_status)
    else:
        normalized_status = ''
    return query, {
        'search': normalized_search,
        'tenant_id': normalized_tenant_id,
        'environment': normalized_environment,
        'status': normalized_status,
    }


def _namespace_profile_lineage(record: TenantNamespace) -> Mapping[str, Any]:
    evidence = record.provisioning_evidence_json or {}
    allocation = evidence.get('allocation') if isinstance(evidence, Mapping) else {}
    allocation = allocation if isinstance(allocation, Mapping) else {}
    lineage = allocation.get('profile_lineage')
    return lineage if isinstance(lineage, Mapping) else {}


def _namespace_profile_name(record: TenantNamespace) -> str:
    if record.resource_profile is not None:
        return record.resource_profile.name
    return str(_namespace_profile_lineage(record).get('label') or 'Imported Provider Baseline')


def _namespace_profile_version(record: TenantNamespace) -> object:
    if record.resource_profile_version:
        return record.resource_profile_version
    return _namespace_profile_lineage(record).get('profile_version')


def _namespace_allocation_state(namespace_options: list[TenantNamespace]) -> dict[str, dict[str, Any]]:
    return {
        str(record.id): {
            'namespace': record.namespace,
            'profile_id': str(record.resource_profile_id) if record.resource_profile_id is not None else None,
            'profile_name': _namespace_profile_name(record),
            'profile_version': _namespace_profile_version(record),
            'quota': record.allocation_quota_json or {},
            'limits': record.allocation_limit_defaults_json or {},
            'storage_policy': record.allocation_storage_policy_json or {},
            'control_state': allocation_control_state(record),
        }
        for record in namespace_options
    }


def get_namespace_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    tenant_id: str = '',
    environment: str = '',
    status: str = '',
    include_workflow_support: bool = True,
) -> dict[str, Any]:
    query, filters = _namespace_registry_query(
        search=search,
        tenant_id=tenant_id,
        environment=environment,
        status=status,
    )
    items, pagination = paginate_query(
        query.order_by(TenantNamespace.created_at.desc(), TenantNamespace.id.desc()),
        page=page,
        per_page=per_page,
    )

    base_context = {
        'namespaces': items,
        'namespace_pagination': pagination,
        'namespace_registry_filters': filters,
        'namespace_registry_tenant_options': (
            Tenant.query.filter(Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value)
            .order_by(Tenant.name.asc())
            .all()
        ),
        'namespace_status_filter_options': [item.value for item in TenantNamespaceProvisioningStatus],
        'namespace_environment_filter_options': sorted(_ALLOWED_ENVIRONMENTS),
    }
    if not include_workflow_support:
        return base_context

    namespace_options = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).all()
    namespace_allocation_options = [
        record
        for record in namespace_options
        if allocation_control_state(record) == 'kaori_managed'
        and record.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
    ]
    namespace_cutover_options = [
        record
        for record in namespace_options
        if record.ownership_status == TenantOwnershipStatus.ADOPTED.value
        and allocation_control_state(record) not in {'kaori_managed', 'provider_mirrored_policy'}
        and record.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value
    ]
    namespace_cutover_state = {
        str(record.id): build_allocation_cutover_state(record) for record in namespace_cutover_options
    }
    profile_options = (
        TenantResourceProfile.query.filter_by(enabled=True).order_by(TenantResourceProfile.name.asc()).all()
    )
    return {
        **base_context,
        'namespace_options': namespace_options,
        'namespace_allocation_options': namespace_allocation_options,
        'namespace_cutover_options': namespace_cutover_options,
        'namespace_cutover_state': namespace_cutover_state,
        'namespace_cutover_supported': any(item['supported'] for item in namespace_cutover_state.values()),
        'profiles': profile_options,
        'namespace_allocation_state': _namespace_allocation_state(namespace_options),
        'namespace_allocation_profiles': {
            str(profile.id): {
                'quota': profile.quota_hard_json or {},
                'limits': profile.limit_defaults_json or {},
                'storage_policy': getattr(profile, 'storage_policy_json', {}) or {},
                'version': int(profile.version or 1),
                'profile_class': profile.profile_class,
                'advanced_controls': profile.advanced_controls_json or {},
            }
            for profile in profile_options
        },
    }


def get_tenant_context() -> dict[str, Any]:
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all()
    profiles = TenantResourceProfile.query.order_by(TenantResourceProfile.created_at.desc()).limit(5).all()
    namespaces = TenantNamespace.query.order_by(TenantNamespace.created_at.desc()).limit(5).all()
    environment_options = _ready_tenant_environment_options()
    ready_clusters = get_ready_native_clusters()
    registered_clusters = (
        Cluster.query.join(KubernetesConnection, KubernetesConnection.cluster_id == Cluster.id)
        .order_by(Cluster.name.asc(), Cluster.id.asc())
        .all()
    )
    capacity_governance = [
        {'cluster': cluster, **build_capacity_governance_summary(cluster.id)} for cluster in registered_clusters
    ]
    capacity_decisions = TenantCapacityDecision.query.order_by(TenantCapacityDecision.created_at.desc()).limit(5).all()
    namespace_count = TenantNamespace.query.filter(TenantNamespace.provisioning_status != 'deprovisioned').count()
    profile_count = TenantResourceProfile.query.count()
    enabled_profile_count = TenantResourceProfile.query.filter_by(enabled=True).count()
    custom_profile_count = TenantResourceProfile.query.filter_by(
        profile_class=TenantResourceProfileClass.CUSTOM.value
    ).count()
    active_profile_allocation_count = TenantNamespace.query.filter(
        TenantNamespace.provisioning_status.notin_(
                    (TenantNamespaceProvisioningStatus.DEPROVISIONED.value, TenantNamespaceProvisioningStatus.RELEASED.value)
                ),
        TenantNamespace.resource_profile_id.isnot(None),
    ).count()
    return {
        'tenants': tenants,
        'profiles': profiles,
        'namespaces': namespaces,
        'environment_options': environment_options,
        'ready_clusters': ready_clusters,
        'registered_clusters': registered_clusters,
        'capacity_governance': capacity_governance,
        'capacity_policy_state': {
            str(item['cluster'].id): item['policy'] for item in capacity_governance if item.get('policy') is not None
        },
        'capacity_decisions': capacity_decisions,
        'tenant_count': Tenant.query.filter(
            Tenant.lifecycle_status != TenantLifecycleStatus.DECOMMISSIONED.value
        ).count(),
        'profile_count': profile_count,
        'resource_profile_stats': {
            'total': profile_count,
            'enabled': enabled_profile_count,
            'custom': custom_profile_count,
            'active_allocations': active_profile_allocation_count,
        },
        'namespace_count': namespace_count,
        'ready_namespace_count': TenantNamespace.query.filter_by(provisioning_status='ready').count(),
        'namespace_drift_rows': (
            TenantNamespace.query.filter_by(provisioning_status=TenantNamespaceProvisioningStatus.DRIFTED.value)
            .order_by(TenantNamespace.updated_at.desc(), TenantNamespace.id.desc())
            .limit(20)
            .all()
        ),
        'native_available': bool(ready_clusters),
        'resource_profile_presets': RESOURCE_PROFILE_PRESETS,
        'resource_profile_advanced_controls': RESOURCE_PROFILE_ADVANCED_CONTROLS,
        'tenant_environment_advanced_control_state': {
            str(environment.id): {
                'tenant_id': environment.tenant_id,
                'provider_key': environment.tenant.provider_key,
                'provider_state': environment.tenant.provider_state,
                'controls': evaluate_resource_profile_advanced_controls(
                    {key: True for key in RESOURCE_PROFILE_ADVANCED_CONTROLS},
                    provider_key=environment.tenant.provider_key,
                    capability_statuses=_tenant_capability_statuses(environment.tenant),
                ),
            }
            for environment in environment_options
        },
        'namespace_allocation_state': {
            str(record.id): {
                'namespace': record.namespace,
                'profile_id': str(record.resource_profile_id) if record.resource_profile_id is not None else None,
                'profile_name': record.resource_profile.name if record.resource_profile is not None else 'Unknown',
                'profile_version': record.resource_profile_version,
                'quota': record.allocation_quota_json or {},
                'limits': record.allocation_limit_defaults_json or {},
                'storage_policy': record.allocation_storage_policy_json or {},
            }
            for record in namespaces
        },
        'namespace_allocation_profiles': {
            str(profile.id): {
                'quota': profile.quota_hard_json or {},
                'limits': profile.limit_defaults_json or {},
                'storage_policy': getattr(profile, 'storage_policy_json', {}) or {},
                'version': int(profile.version or 1),
                'profile_class': profile.profile_class,
                'advanced_controls': profile.advanced_controls_json or {},
            }
            for profile in profiles
            if profile.enabled
        },
    }
