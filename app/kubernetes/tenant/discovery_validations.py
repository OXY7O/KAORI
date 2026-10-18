from __future__ import annotations

from app.models.tenant import Tenant, TenantLifecycleStatus


def validate_existing_tenant_attachment_target(tenant: Tenant, *, cluster_id: str, namespace: str) -> None:
    if not namespace or str(tenant.cluster_id) != cluster_id:
        raise ValueError('Namespace and existing Tenant must belong to the same cluster.')
    if (
        tenant.lifecycle_status != TenantLifecycleStatus.READY.value
        or tenant.provider_key != 'native_kubernetes'
        or tenant.provider_state != 'native'
        or tenant.reconciliation_authority != 'native_kubernetes'
    ):
        raise ValueError('The selected Tenant is not Ready under Native Kubernetes authority.')


def validate_namespace_attachment_uid(*, observed_uid: str, expected_uid: str) -> None:
    if not observed_uid or not expected_uid or observed_uid != expected_uid:
        raise ValueError('Namespace UID changed since adoption preflight; refresh Discovery.')


