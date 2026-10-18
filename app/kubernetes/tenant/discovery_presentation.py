from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import capsule_namespace_authority_present
from app.models.tenant import Tenant, TenantNamespace

_SYSTEM_NAMESPACES = frozenset({'default', 'kube-system', 'kube-public', 'kube-node-lease'})


def _namespace_phase(item: Any) -> str:
    metadata = getattr(item, 'metadata', None)
    status = getattr(item, 'status', None)
    if getattr(metadata, 'deletion_timestamp', None):
        return 'Terminating'
    return str(getattr(status, 'phase', None) or 'Present')


def _capsule_phase(item: dict[str, Any]) -> str:
    metadata = item.get('metadata') if isinstance(item, dict) else {}
    status = item.get('status') if isinstance(item, dict) else {}
    if isinstance(metadata, dict) and metadata.get('deletionTimestamp'):
        return 'Terminating'
    if isinstance(status, dict):
        for key in ('state', 'phase'):
            value = status.get(key)
            if value:
                return str(value)
        conditions = status.get('conditions')
        if isinstance(conditions, list):
            for condition in conditions:
                if not isinstance(condition, dict):
                    continue
                if condition.get('status') == 'True' and condition.get('type'):
                    return str(condition['type'])
    return 'Observed'


def _tone(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {'active', 'ready', 'observed', 'present'}:
        return 'normal'
    if normalized in {'terminating', 'degraded', 'failed', 'error'}:
        return 'critical'
    return 'warning'


def _unclaimed_provider_ownership_reason(*, labels: Mapping[str, Any], resource_kind: str) -> str | None:
    """Reject orphaned KAORI labels and foreign managers before any provider takeover."""
    manager = str(labels.get('app.kubernetes.io/managed-by') or '').strip()
    reserved_claims = (
        'kaori.io/tenant-id',
        'kaori.io/tenant-generation',
        'kaori.io/environment',
        'kaori.io/resource-profile',
    )
    if manager.lower() == 'kaori' or any(key in labels for key in reserved_claims):
        return (
            f'{resource_kind} has KAORI ownership markers without active governance; '
            'inspect provider residue and recover the prior Tenant before adoption.'
        )
    if manager:
        return f'{resource_kind} declares external manager {manager}.'
    return None


def _native_management(
    *,
    namespace: str,
    labels: dict[str, str],
    managed_record: TenantNamespace | None,
    owner_references: Any = None,
) -> tuple[str, str]:
    if managed_record is not None:
        return 'Managed', 'Already governed by KAORI.'
    if namespace in _SYSTEM_NAMESPACES:
        return 'Blocked', 'Kubernetes system namespaces are not Tenant adoption candidates.'
    if capsule_namespace_authority_present(
        labels=labels,
        owner_references=owner_references,
    ):
        return 'Blocked', 'Namespace remains correlated to Capsule Tenant authority; use Capsule governance.'
    ownership_reason = _unclaimed_provider_ownership_reason(labels=labels, resource_kind='Namespace')
    if ownership_reason:
        return 'Blocked', ownership_reason
    return 'Discovered', 'Candidate for governed adoption preflight; no provider mutation has occurred.'


def _managed_capsule_map(cluster_ids: list[str]) -> dict[tuple[str, str], Tenant]:
    if not cluster_ids:
        return {}
    rows = Tenant.query.filter(
        Tenant.cluster_id.in_(cluster_ids),
        Tenant.provider_key == 'capsule',
        Tenant.lifecycle_status.notin_(('decommissioned', 'released')),
    ).all()
    result: dict[tuple[str, str], Tenant] = {}
    for tenant in rows:
        for reference in {str(tenant.provider_reference or '').strip(), tenant.slug, tenant.name}:
            if reference:
                result[(str(tenant.cluster_id), reference)] = tenant
    return result
