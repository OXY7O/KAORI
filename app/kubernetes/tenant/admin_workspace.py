from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_

from app.common.pagination import paginate_query, paginate_sequence
from app.kubernetes.tenant.credential import build_namespace_access_package, credential_target_namespaces
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantCredential,
    TenantEnvironment,
    TenantGroup,
    TenantMembership,
    TenantNamespace,
)


def get_tenant_summary_context() -> dict[str, int]:
    """Return bounded page-level Tenant governance counters from committed KAORI state."""

    return {
        'tenant_summary_tenant_count': Tenant.query.filter(Tenant.lifecycle_status != 'decommissioned').count(),
        'tenant_summary_environment_count': (
            TenantEnvironment.query.join(Tenant, Tenant.id == TenantEnvironment.tenant_id)
            .filter(Tenant.lifecycle_status != 'decommissioned')
            .count()
        ),
        'tenant_summary_namespace_count': TenantNamespace.query.count(),
        'tenant_summary_membership_count': TenantMembership.query.filter_by(status='active').count(),
        'tenant_summary_access_grant_count': TenantAccessGrant.query.filter_by(status='active').count(),
        'tenant_summary_credential_count': TenantCredential.query.filter(
            TenantCredential.status.in_(('active', 'renewal_due', 'rotating', 'suspended'))
        ).count(),
    }


def _tenant_options() -> list[Tenant]:
    return (
        Tenant.query.filter(Tenant.lifecycle_status != 'decommissioned')
        .order_by(Tenant.name.asc())
        .all()
    )


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
    query = (
        TenantAccessGrant.query.join(Tenant, Tenant.id == TenantAccessGrant.tenant_id)
        .join(TenantMembership, TenantMembership.id == TenantAccessGrant.membership_id)
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
    return {
        'credential_rows': items,
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
