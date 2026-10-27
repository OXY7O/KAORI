from __future__ import annotations

from typing import Any

import yaml
from sqlalchemy import func, or_

from app.common.pagination import paginate_query, paginate_sequence
from app.extensions.db import db
from app.kubernetes.tenant.access import (
    ACCESS_PROFILE_CATALOG,
    LATEST_ACCESS_PROFILE_VERSION,
    capsule_cluster_role_manifest,
)
from app.kubernetes.tenant.credential import (
    build_namespace_access_package,
    credential_material_ttl_choices,
    credential_material_ttl_policy,
    credential_target_namespaces,
)
from app.models import AuditEvent, User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantCredential,
    TenantEnvironment,
    TenantGroup,
    TenantLifecycleStatus,
    TenantMembership,
    TenantMembershipStatus,
    TenantNamespace,
)


def get_tenant_summary_context() -> dict[str, int]:
    """Return bounded page-level Tenant governance counters from committed KAORI state."""

    return {
        'tenant_summary_tenant_count': Tenant.query.filter(
            Tenant.lifecycle_status.notin_(('decommissioned', 'released'))
        ).count(),
        'tenant_summary_environment_count': (
            TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
            .filter(Tenant.lifecycle_status.notin_(('decommissioned', 'released')))
            .count()
        ),
        'tenant_summary_namespace_count': TenantNamespace.query.filter(
            TenantNamespace.provisioning_status.notin_(('deprovisioned', 'released'))
        ).count(),
        'tenant_summary_membership_count': TenantMembership.query.filter_by(status='active').count(),
        'tenant_summary_access_grant_count': TenantAccessGrant.query.filter_by(status='active').count(),
        'tenant_summary_credential_count': TenantCredential.query.filter(
            TenantCredential.status.in_(('active', 'renewal_due', 'rotating', 'suspended'))
        ).count(),
    }


def _tenant_options() -> list[Tenant]:
    return Tenant.query.filter(Tenant.lifecycle_status == 'ready').order_by(Tenant.name.asc()).all()


def get_membership_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    tenant_id: str = '',
    principal_type: str = '',
    status: str = '',
    search: str = '',
) -> dict[str, Any]:
    query = TenantMembership.query.join(Tenant, Tenant.id == TenantMembership.tenant_id)
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_principal = principal_type.strip().lower()
    normalized_status = status.strip().lower()

    if normalized_tenant_id:
        query = query.filter(TenantMembership.tenant_id == normalized_tenant_id)
    if normalized_principal:
        query = query.filter(TenantMembership.principal_type == normalized_principal)
    if normalized_status:
        query = query.filter(TenantMembership.status == normalized_status)
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantMembership.subject_name).like(pattern),
                func.lower(Tenant.name).like(pattern),
            )
        )

    items, pagination = paginate_query(
        query.order_by(TenantMembership.updated_at.desc(), TenantMembership.id.desc()),
        page=page,
        per_page=per_page,
    )
    return {
        'membership_rows': items,
        'membership_pagination': pagination,
        'membership_filters': {
            'tenant_id': normalized_tenant_id,
            'principal_type': normalized_principal,
            'status': normalized_status,
            'search': normalized_search,
        },
        'membership_tenant_options': _tenant_options(),
        'membership_principal_options': ('user', 'group', 'service_account'),
        'membership_status_options': ('active', 'revoked'),
    }


def get_group_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    tenant_id: str = '',
    enabled: str = '',
    search: str = '',
) -> dict[str, Any]:
    query = TenantGroup.query.join(Tenant, Tenant.id == TenantGroup.tenant_id)
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_enabled = enabled.strip().lower()

    if normalized_tenant_id:
        query = query.filter(TenantGroup.tenant_id == normalized_tenant_id)
    if normalized_enabled in {'enabled', 'disabled'}:
        query = query.filter(TenantGroup.enabled.is_(normalized_enabled == 'enabled'))
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantGroup.name).like(pattern),
                func.lower(TenantGroup.subject_name).like(pattern),
                func.lower(Tenant.name).like(pattern),
            )
        )

    items, pagination = paginate_query(
        query.order_by(TenantGroup.updated_at.desc(), TenantGroup.id.desc()),
        page=page,
        per_page=per_page,
    )
    return {
        'group_rows': items,
        'group_pagination': pagination,
        'group_filters': {
            'tenant_id': normalized_tenant_id,
            'enabled': normalized_enabled,
            'search': normalized_search,
        },
        'group_tenant_options': _tenant_options(),
        'group_enabled_options': ('enabled', 'disabled'),
    }


def get_access_grant_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    tenant_id: str = '',
    status: str = '',
    reconciliation_status: str = '',
    scope_type: str = '',
    search: str = '',
) -> dict[str, Any]:
    query = TenantAccessGrant.query.join(Tenant, Tenant.id == TenantAccessGrant.tenant_id).join(
        TenantMembership, TenantMembership.id == TenantAccessGrant.membership_id
    )
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_status = status.strip().lower()
    normalized_reconciliation = reconciliation_status.strip().lower()
    normalized_scope = scope_type.strip().lower()

    if normalized_tenant_id:
        query = query.filter(TenantAccessGrant.tenant_id == normalized_tenant_id)
    if normalized_status:
        query = query.filter(TenantAccessGrant.status == normalized_status)
    if normalized_reconciliation:
        query = query.filter(TenantAccessGrant.reconciliation_status == normalized_reconciliation)
    if normalized_scope:
        query = query.filter(TenantAccessGrant.scope_type == normalized_scope)
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantMembership.subject_name).like(pattern),
                func.lower(Tenant.name).like(pattern),
                func.lower(TenantAccessGrant.access_profile).like(pattern),
            )
        )

    items, pagination = paginate_query(
        query.order_by(TenantAccessGrant.updated_at.desc(), TenantAccessGrant.id.desc()),
        page=page,
        per_page=per_page,
    )
    return {
        'access_grant_rows': items,
        'access_grant_pagination': pagination,
        'access_grant_filters': {
            'tenant_id': normalized_tenant_id,
            'status': normalized_status,
            'reconciliation_status': normalized_reconciliation,
            'scope_type': normalized_scope,
            'search': normalized_search,
        },
        'access_grant_tenant_options': _tenant_options(),
        'access_grant_status_options': ('active', 'revoked'),
        'access_grant_reconciliation_options': ('pending', 'ready', 'drifted', 'failed', 'revoked'),
        'access_grant_scope_options': ('tenant', 'environment', 'namespace'),
    }


def get_credential_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    tenant_id: str = '',
    credential_type: str = '',
    status: str = '',
    search: str = '',
) -> dict[str, Any]:
    query = TenantCredential.query.join(Tenant, Tenant.id == TenantCredential.tenant_id)
    normalized_search = search.strip()
    normalized_tenant_id = tenant_id.strip()
    normalized_type = credential_type.strip().lower()
    normalized_status = status.strip().lower()

    if normalized_tenant_id:
        query = query.filter(TenantCredential.tenant_id == normalized_tenant_id)
    if normalized_type:
        query = query.filter(TenantCredential.credential_type == normalized_type)
    if normalized_status:
        query = query.filter(TenantCredential.status == normalized_status)
    if normalized_search:
        pattern = f'%{normalized_search.lower()}%'
        query = query.filter(
            or_(
                func.lower(TenantCredential.service_account_name).like(pattern),
                func.lower(TenantCredential.purpose).like(pattern),
                func.lower(TenantCredential.application_name).like(pattern),
                func.lower(Tenant.name).like(pattern),
            )
        )

    items, pagination = paginate_query(
        query.order_by(TenantCredential.updated_at.desc(), TenantCredential.id.desc()),
        page=page,
        per_page=per_page,
    )
    delivery_targets: dict[str, list[TenantNamespace]] = {}
    delivery_policies: dict[str, dict[str, dict[str, object]]] = {}
    for credential in items:
        try:
            targets = credential_target_namespaces(credential)
        except ValueError:
            targets = []
        delivery_targets[str(credential.id)] = targets
        delivery_policies[str(credential.id)] = {
            str(namespace.id): credential_material_ttl_policy(namespace.environment.environment)
            for namespace in targets
        }

    return {
        'credential_rows': items,
        'credential_delivery_targets': delivery_targets,
        'credential_delivery_policies': delivery_policies,
        'credential_material_ttl_choices': credential_material_ttl_choices(),
        'credential_pagination': pagination,
        'credential_filters': {
            'tenant_id': normalized_tenant_id,
            'credential_type': normalized_type,
            'status': normalized_status,
            'search': normalized_search,
        },
        'credential_tenant_options': _tenant_options(),
        'credential_type_options': (
            'human_service_account',
            'admin_kubeconfig',
            'deployer_service_account',
        ),
        'credential_status_options': (
            'active',
            'renewal_due',
            'rotating',
            'suspended',
            'expired',
            'revoked',
        ),
    }


def get_namespace_access_registry_context(
    *,
    page: int = 1,
    per_page: int = 5,
    tenant_id: str = '',
    environment: str = '',
    credential_status: str = '',
    search: str = '',
) -> dict[str, Any]:
    normalized_search = search.strip().lower()
    normalized_tenant_id = tenant_id.strip()
    normalized_environment = environment.strip().lower()
    normalized_status = credential_status.strip().lower()

    credential_query = TenantCredential.query.order_by(
        TenantCredential.updated_at.desc(),
        TenantCredential.id.desc(),
    )
    if normalized_tenant_id:
        credential_query = credential_query.filter(TenantCredential.tenant_id == normalized_tenant_id)
    if normalized_status:
        credential_query = credential_query.filter(TenantCredential.status == normalized_status)

    rows: list[dict[str, Any]] = []
    for credential in credential_query.all():
        try:
            targets = credential_target_namespaces(credential)
            if not targets:
                rows.append(
                    {
                        'tenant_id': credential.tenant_id,
                        'tenant_name': credential.tenant.name,
                        'environment': '',
                        'namespace': '',
                        'cluster_name': '',
                        'service_account_name': credential.service_account_name,
                        'credential_type': credential.credential_type,
                        'credential_status': credential.status,
                        'access_profile': '',
                        'approved_access_methods': [],
                        'renewal_due_at': credential.renewal_due_at.isoformat(),
                        'valid_until': credential.valid_until.isoformat(),
                        'actions': [],
                        'error': 'No managed namespace is currently inside this credential scope.',
                    }
                )
                continue
            for namespace in targets:
                rows.append(build_namespace_access_package(credential, namespace).as_dict())
        except ValueError as exc:
            rows.append(
                {
                    'tenant_id': credential.tenant_id,
                    'tenant_name': credential.tenant.name,
                    'environment': '',
                    'namespace': '',
                    'cluster_name': '',
                    'service_account_name': credential.service_account_name,
                    'credential_type': credential.credential_type,
                    'credential_status': credential.status,
                    'access_profile': '',
                    'approved_access_methods': [],
                    'renewal_due_at': credential.renewal_due_at.isoformat(),
                    'valid_until': credential.valid_until.isoformat(),
                    'actions': [],
                    'error': str(exc),
                }
            )

    if normalized_environment:
        rows = [row for row in rows if str(row.get('environment') or '').lower() == normalized_environment]
    if normalized_search:
        rows = [
            row
            for row in rows
            if normalized_search
            in ' '.join(
                str(row.get(key) or '').lower()
                for key in ('tenant_name', 'namespace', 'cluster_name', 'service_account_name', 'access_profile')
            )
        ]

    paged_rows, pagination = paginate_sequence(rows, page=page, per_page=per_page)
    return {
        'namespace_access_registry_rows': paged_rows,
        'namespace_access_pagination': pagination,
        'namespace_access_filters': {
            'tenant_id': normalized_tenant_id,
            'environment': normalized_environment,
            'credential_status': normalized_status,
            'search': search.strip(),
        },
        'namespace_access_tenant_options': _tenant_options(),
        'namespace_access_environment_options': ('development', 'staging', 'production'),
        'namespace_access_status_options': (
            'active',
            'renewal_due',
            'rotating',
            'suspended',
            'expired',
            'revoked',
        ),
    }


def _remediation_matches_access_observation(
    *,
    provider: str,
    observation: dict[str, object],
    drift: dict[str, object],
    plan: dict[str, object],
) -> bool:
    """Display a decision only with its exact committed drift and provider observation."""
    provider_key = 'capsule' if provider == 'capsule' else 'native_kubernetes'
    drift_type = (
        'kubernetes_tenant_access_drift_evidence'
        if provider == 'capsule'
        else 'kubernetes_tenant_native_access_drift_evidence'
    )
    source_observed_at = drift.get('source_observed_at') or drift.get('observation_checked_at')
    if not (
        plan.get('tenant_id')
        and plan.get('tenant_id') == observation.get('tenant_id') == drift.get('tenant_id')
        and plan.get('cluster_id') == observation.get('cluster_id') == drift.get('cluster_id')
        and plan.get('provider') == provider_key
        and plan.get('source_target_type') == drift_type
        and plan.get('source_drift_evaluated_at')
        and plan.get('source_drift_evaluated_at') == drift.get('evaluated_at')
        and source_observed_at
        and source_observed_at == observation.get('observed_at')
        and plan.get('auto_mutation_performed') is False
    ):
        return False
    if provider == 'native':
        return bool(
            observation.get('evidence_sha256')
            and observation.get('evidence_sha256') == drift.get('source_evidence_sha256')
        )
    return bool(
        observation.get('provider_uid')
        and observation.get('resource_version')
        and observation.get('provider_uid') == drift.get('observation_uid')
        and observation.get('resource_version') == drift.get('observation_resource_version')
    )


def get_provider_access_evidence_registry_context(
    *,
    provider: str,
    page: int = 1,
    per_page: int = 5,
    search: str = '',
    status: str = '',
) -> dict[str, object]:
    """Page committed inspection AuditEvents for one provider; never query Kubernetes."""
    target_types = {
        'capsule': 'kubernetes_tenant_external_access_inventory',
        'native': 'kubernetes_tenant_native_external_access_inventory',
    }
    if provider not in target_types:
        raise ValueError('Unknown Tenant access inspection provider.')

    search_value = search.strip()[:120]
    status_value = status if status in {'observed', 'review_required'} else ''
    query = AuditEvent.query.filter(AuditEvent.target_type == target_types[provider])
    total_committed = query.count()
    total_review_required = query.filter(AuditEvent.metadata_json['status'].as_string() == 'review_required').count()
    if status_value:
        query = query.filter(AuditEvent.metadata_json['status'].as_string() == status_value)
    if search_value:
        pattern = f'%{search_value}%'
        query = query.filter(
            or_(
                AuditEvent.metadata_json['tenant_id'].as_string().ilike(pattern),
                AuditEvent.summary.ilike(pattern),
            )
        )
    rows, pagination = paginate_query(
        query.order_by(AuditEvent.id.desc()),
        page=page,
        per_page=per_page,
    )
    # Drift findings are separate committed analyses, not part of an inspection.
    # Resolve the newest per Tenant on the current page without N+1 provider reads.
    drift_by_tenant: dict[str, AuditEvent] = {}
    tenant_ids = {
        str((event.metadata_json or {}).get('tenant_id'))
        for event in rows
        if (event.metadata_json or {}).get('tenant_id')
    }
    drift_types = {
        'capsule': 'kubernetes_tenant_access_drift_evidence',
        'native': 'kubernetes_tenant_native_access_drift_evidence',
    }
    if tenant_ids:
        tenant_key = AuditEvent.metadata_json['tenant_id'].as_string()
        latest_ids = (
            db.session.query(
                AuditEvent.id.label('audit_event_id'),
                func.row_number().over(partition_by=tenant_key, order_by=AuditEvent.id.desc()).label('row_number'),
            )
            .filter(
                AuditEvent.target_type == drift_types[provider],
                tenant_key.in_(tenant_ids),
            )
            .subquery()
        )
        drift_events = (
            AuditEvent.query.join(latest_ids, AuditEvent.id == latest_ids.c.audit_event_id)
            .filter(latest_ids.c.row_number == 1)
            .all()
        )
        drift_by_tenant = {str((event.metadata_json or {}).get('tenant_id')): event for event in drift_events}
    # Latest committed remediation is resolved by exact Tenant + provider in a
    # single page-scoped query. Do not reuse the global recent-plan sidebar feed.
    remediation_by_observation: dict[int, AuditEvent] = {}
    if tenant_ids:
        provider_key = 'capsule' if provider == 'capsule' else 'native_kubernetes'
        latest_plan_ids = (
            db.session.query(
                AuditEvent.id.label('audit_event_id'),
                func.row_number()
                .over(partition_by=AuditEvent.target_id, order_by=AuditEvent.id.desc())
                .label('row_number'),
            )
            .filter(
                AuditEvent.target_type == 'kubernetes_tenant_access_remediation_plan',
                AuditEvent.target_id.in_(tenant_ids),
                AuditEvent.metadata_json['provider'].as_string() == provider_key,
            )
            .subquery()
        )
        latest_plans = (
            AuditEvent.query.join(latest_plan_ids, AuditEvent.id == latest_plan_ids.c.audit_event_id)
            .filter(latest_plan_ids.c.row_number == 1)
            .all()
        )
        plans_by_tenant = {event.target_id: event for event in latest_plans}
        for observation_event in rows:
            observation = observation_event.metadata_json or {}
            tenant_id = str(observation.get('tenant_id') or '')
            drift_event = drift_by_tenant.get(tenant_id)
            plan_event = plans_by_tenant.get(tenant_id)
            if not drift_event or not plan_event:
                continue
            if _remediation_matches_access_observation(
                provider=provider,
                observation=observation,
                drift=drift_event.metadata_json or {},
                plan=plan_event.metadata_json or {},
            ):
                remediation_by_observation[observation_event.id] = plan_event

    return {
        'access_evidence_remediation_by_observation': remediation_by_observation,
        'access_evidence_drift_by_tenant': drift_by_tenant,
        'access_evidence_total': total_committed,
        'access_evidence_review_required': total_review_required,
        'access_evidence_rows': rows,
        'access_evidence_pagination': pagination,
        'access_evidence_filters': {'search': search_value, 'status': status_value},
    }


def get_tenant_access_context() -> dict[str, object]:
    tenant_options = (
        Tenant.query.filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc())
        .all()
    )
    user_options = (
        User.query.filter(User.account_is_active.is_(True), User.deleted_at.is_(None))
        .order_by(User.username.asc())
        .all()
    )
    group_options = (
        TenantGroup.query.join(Tenant, Tenant.id == TenantGroup.tenant_id)
        .filter(
            TenantGroup.enabled.is_(True),
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
        )
        .order_by(TenantGroup.name.asc())
        .all()
    )
    membership_options = (
        TenantMembership.query.join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .filter(
            TenantMembership.status == TenantMembershipStatus.ACTIVE.value,
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
        )
        .order_by(TenantMembership.created_at.desc())
        .all()
    )
    environment_options = (
        TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(Tenant.lifecycle_status == TenantLifecycleStatus.READY.value)
        .order_by(Tenant.name.asc(), TenantEnvironment.environment.asc())
        .all()
    )
    namespace_options = (
        TenantNamespace.query.join(TenantEnvironment, TenantEnvironment.id == TenantNamespace.tenant_environment_id)
        .join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
        .filter(
            Tenant.lifecycle_status == TenantLifecycleStatus.READY.value,
            TenantNamespace.provisioning_status == 'ready',
        )
        .order_by(Tenant.name.asc(), TenantNamespace.namespace.asc())
        .all()
    )
    profile_order = ('viewer', 'operator', 'tenant_admin', 'deployer')
    profiles = [
        ACCESS_PROFILE_CATALOG[(key, LATEST_ACCESS_PROFILE_VERSION[key])]
        for key in profile_order
        if key in LATEST_ACCESS_PROFILE_VERSION
    ]
    capsule_role_documents = [capsule_cluster_role_manifest(profile) for profile in profiles]
    capsule_role_manifests = [
        {
            'label': profile.label,
            'version': profile.version,
            'name': document['metadata']['name'],
            'yaml': yaml.safe_dump(document, sort_keys=False, explicit_start=True),
        }
        for profile, document in zip(profiles, capsule_role_documents, strict=True)
    ]
    recent_access_remediation = (
        AuditEvent.query.filter_by(target_type='kubernetes_tenant_access_remediation_plan')
        .order_by(AuditEvent.id.desc())
        .limit(30)
        .all()
    )
    capsule_remediation = [
        row for row in recent_access_remediation if (row.metadata_json or {}).get('provider', 'capsule') == 'capsule'
    ][:5]
    native_remediation = [
        row for row in recent_access_remediation if (row.metadata_json or {}).get('provider') == 'native_kubernetes'
    ][:5]
    return {
        'access_tenant_options': tenant_options,
        'access_user_options': user_options,
        'access_group_options': group_options,
        'access_membership_options': membership_options,
        'access_environment_options': environment_options,
        'access_namespace_options': namespace_options,
        'access_profiles': profiles,
        'access_capsule_role_manifests': capsule_role_manifests,
        'access_capsule_role_bundle_yaml': yaml.safe_dump_all(
            capsule_role_documents, sort_keys=False, explicit_start=True
        ),
        'recent_tenant_groups': TenantGroup.query.order_by(TenantGroup.created_at.desc()).limit(5).all(),
        'recent_tenant_memberships': TenantMembership.query.order_by(TenantMembership.created_at.desc()).limit(5).all(),
        'recent_access_grants': TenantAccessGrant.query.order_by(TenantAccessGrant.created_at.desc()).limit(5).all(),
        'external_capsule_tenants': [
            tenant
            for tenant in tenant_options
            if tenant.provider_key == 'capsule' and tenant.provider_state == 'capsule'
        ],
        'external_native_tenants': [
            tenant
            for tenant in tenant_options
            if tenant.provider_key == 'native_kubernetes'
            and tenant.provider_state == 'native'
            and tenant.reconciliation_authority == 'native_kubernetes'
        ],
        'recent_external_access_profile_reviews': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_external_role_profile_review')
            .order_by(AuditEvent.id.desc())
            .limit(5)
            .all()
        ),
        'recent_external_native_access': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_native_external_access_inventory')
            .order_by(AuditEvent.id.desc())
            .limit(5)
            .all()
        ),
        'recent_external_capsule_access': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_external_access_inventory')
            .order_by(AuditEvent.id.desc())
            .limit(5)
            .all()
        ),
        'recent_capsule_access_drift': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_access_drift_evidence')
            .order_by(AuditEvent.id.desc())
            .limit(5)
            .all()
        ),
        'recent_native_access_drift': (
            AuditEvent.query.filter_by(target_type='kubernetes_tenant_native_access_drift_evidence')
            .order_by(AuditEvent.id.desc())
            .limit(5)
            .all()
        ),
        'recent_capsule_access_remediation': capsule_remediation,
        'recent_native_access_remediation': native_remediation,
    }
