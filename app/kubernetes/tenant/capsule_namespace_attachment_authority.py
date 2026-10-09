"""Immutable provider-authority checks for attaching a Namespace to an existing Capsule Tenant.

This pure validation contract never mutates a Capsule Tenant, Namespace,
RoleBinding, profile, or KAORI Tenant state. Capsule stays authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS


def _value(obj: Any, attr: str) -> Any:
    return obj.get(attr) if isinstance(obj, Mapping) else getattr(obj, attr, None)


def _text(obj: Any, attr: str, *, alt: str = '') -> str:
    return str(_value(obj, attr) or (_value(obj, alt) if alt else '') or '').strip()


def validate_capsule_existing_tenant_target(
    tenant: Any, *, cluster_id: str, capsule_name: str, capsule_uid: str,
) -> None:
    """Do not reparent a Namespace across Capsule or cluster authority."""
    if not capsule_name or not capsule_uid or str(tenant.cluster_id) != cluster_id:
        raise ValueError('Capsule Namespace attachment requires exact cluster and Tenant identity.')
    if (
        tenant.provider_key != 'capsule'
        or tenant.provider_state != 'capsule'
        or tenant.reconciliation_authority != 'capsule'
        or tenant.lifecycle_status != 'ready'
        or tenant.ownership_status not in {'adopted', 'managed'}
        or str(tenant.provider_reference or '') != capsule_name
        or str((tenant.provider_evidence_json or {}).get('provider_uid') or '') != capsule_uid
    ):
        raise ValueError('Selected Tenant is not Ready under the matching Capsule provider authority.')


def validate_capsule_namespace_attachment(
    *,
    tenant: Any,
    cluster_id: str,
    capsule_item: Mapping[str, Any],
    namespace: Any,
    expected_namespace_uid: str,
    status_namespace_names: set[str],
) -> dict[str, Any]:
    """Verify immutable Capsule Tenant/Namespace linkage and fail closed on ambiguity."""
    capsule_meta = capsule_item.get('metadata') or {}
    if not isinstance(capsule_meta, Mapping):
        raise ValueError('Capsule Tenant provider metadata is malformed.')
    capsule_name = str(capsule_meta.get('name') or '').strip()
    capsule_uid = str(capsule_meta.get('uid') or '').strip()
    capsule_rv = str(capsule_meta.get('resourceVersion') or '').strip()
    validate_capsule_existing_tenant_target(
        tenant, cluster_id=cluster_id, capsule_name=capsule_name, capsule_uid=capsule_uid
    )
    if not capsule_rv:
        raise ValueError('Capsule Tenant resourceVersion is missing.')

    meta = _value(namespace, 'metadata')
    name = _text(meta, 'name')
    uid = _text(meta, 'uid')
    resource_version = _text(meta, 'resource_version', alt='resourceVersion')
    if not name or not uid or not resource_version or uid != expected_namespace_uid:
        raise ValueError('Namespace UID/resourceVersion changed since explicit adoption review.')
    if _text(meta, 'deletion_timestamp', alt='deletionTimestamp'):
        raise ValueError('Terminating Namespace cannot be attached.')
    labels = _value(meta, 'labels') or {}
    if not isinstance(labels, Mapping):
        raise ValueError('Capsule Namespace labels are malformed.')
    claims = {
        str(labels[key]).strip()
        for key in _CAPSULE_TENANT_LABEL_KEYS
        if key in labels and str(labels[key]).strip()
    }
    references = _value(meta, 'owner_references') or _value(meta, 'ownerReferences') or []
    if not isinstance(references, list):
        raise ValueError('Capsule Namespace ownerReferences are malformed.')
    owners = {
        _text(owner, 'name')
        for owner in references
        if _text(owner, 'kind') == 'Tenant'
        and _text(owner, 'api_version', alt='apiVersion').startswith('capsule.clastix.io/')
    }
    if len(claims) > 1 or len(owners) > 1:
        raise ValueError('Namespace has ambiguous Capsule Tenant ownership claims.')
    if claims and claims != {capsule_name}:
        raise ValueError('Namespace Capsule label belongs to another Tenant.')
    if owners and owners != {capsule_name}:
        raise ValueError('Namespace Capsule ownerReference belongs to another Tenant.')
    if not (capsule_name in claims or capsule_name in owners or name in status_namespace_names):
        raise ValueError('Namespace has no authoritative Capsule Tenant correlation.')
    return {
        'namespace': name, 'namespace_uid': uid, 'namespace_resource_version': resource_version,
        'capsule_tenant_name': capsule_name, 'capsule_tenant_uid': capsule_uid,
        'capsule_tenant_resource_version': capsule_rv,
        'authority': 'capsule', 'provider_mutation_performed': False,
    }
