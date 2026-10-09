from __future__ import annotations

from app.kubernetes.tenant.access_reconciliation import inspect_native_access_grant, reconcile_native_access_grant
from app.kubernetes.tenant.capsule_access_reconciliation import (
    inspect_capsule_access_grant,
    reconcile_capsule_access_grant,
)
from app.models.tenant import TenantAccessGrant


def reconcile_provider_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    tenant = grant.tenant
    if tenant.reconciliation_authority != tenant.provider_key:
        raise ValueError('Tenant provider and reconciliation authority disagree; refusing RBAC mutation.')
    if tenant.provider_key == 'native_kubernetes':
        return reconcile_native_access_grant(grant)
    if tenant.provider_key == 'capsule':
        return reconcile_capsule_access_grant(grant)
    raise ValueError('Unsupported Tenant Access Grant provider authority.')


def inspect_provider_access_grant(grant: TenantAccessGrant) -> TenantAccessGrant:
    tenant = grant.tenant
    if tenant.reconciliation_authority != tenant.provider_key:
        raise ValueError('Tenant provider and reconciliation authority disagree; refusing RBAC inspection.')
    if tenant.provider_key == 'native_kubernetes':
        return inspect_native_access_grant(grant)
    if tenant.provider_key == 'capsule':
        return inspect_capsule_access_grant(grant)
    raise ValueError('Unsupported Tenant Access Grant provider authority.')
