"""Read-only, bounded Native Kubernetes Tenant RBAC observation.

External RoleBindings are provider evidence, never automatically imported
as KAORI Memberships or Access Grants. This observer never mutates Kubernetes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.models import Cluster
from app.models.audit import AuditEvent
from app.models.tenant import Tenant, TenantAccessGrant, TenantEnvironment, TenantNamespace

_TARGET = 'kubernetes_tenant_native_external_access_inventory'
_MAX_NAMESPACES = 30
_MAX_BINDINGS = 200
_MANAGER_LABEL = 'app.kubernetes.io/managed-by'
_GRANT_LABEL = 'kaori.io/access-grant'


def _subject(item: Any) -> dict[str, str]:
    kind = str(getattr(item, 'kind', '') or '').strip()
    name = str(getattr(item, 'name', '') or '').strip()
    namespace = str(getattr(item, 'namespace', '') or '').strip()
    if kind not in {'User', 'Group', 'ServiceAccount'} or not name or len(name) > 253:
        raise ValueError('Native RoleBinding has an unsupported/ambiguous subject.')
    if kind == 'ServiceAccount' and (not namespace or len(namespace) > 253):
        raise ValueError('Native RoleBinding ServiceAccount subject requires an explicit namespace.')
    return {'kind': kind, 'name': name, 'namespace': namespace if kind == 'ServiceAccount' else ''}


def normalize_native_role_binding(
    item: Any, *, namespace: str, grant_ids: set[str]
) -> dict[str, Any]:
    """Classify a namespaced binding; labels alone never prove KAORI ownership."""
    meta = getattr(item, 'metadata', None)
    ref = getattr(item, 'role_ref', None)
    name = str(getattr(meta, 'name', '') or '').strip()
    uid = str(getattr(meta, 'uid', '') or '').strip()
    version = str(getattr(meta, 'resource_version', '') or '').strip()
    kind = str(getattr(ref, 'kind', '') or '').strip()
    role_name = str(getattr(ref, 'name', '') or '').strip()
    role_api = str(getattr(ref, 'api_group', '') or '').strip()
    if (
        not name or not uid or not version or not role_name
        or kind not in {'Role', 'ClusterRole'} or role_api != 'rbac.authorization.k8s.io'
    ):
        raise ValueError('Native RoleBinding identity or role reference is unverified.')
    labels = getattr(meta, 'labels', None) or {}
    if not isinstance(labels, Mapping):
        raise ValueError('Native RoleBinding ownership labels are malformed.')
    subjects = getattr(item, 'subjects', None) or []
    if not isinstance(subjects, list) or len(subjects) > 100:
        raise ValueError('Native RoleBinding subjects are unbounded or malformed.')
    marker = str(labels.get(_GRANT_LABEL) or '').strip()
    manager = str(labels.get(_MANAGER_LABEL) or '').strip()
    marked = manager == 'kaori' and bool(marker)
    ambiguous_marker = bool(manager == 'kaori' or marker) and not marked
    correlated = marked and marker in grant_ids
    return {
        'namespace': namespace,
        'name': name,
        'uid': uid,
        'resource_version': version,
        'role_ref': {'kind': kind, 'name': role_name},
        'subjects': [_subject(subject) for subject in subjects],
        'ownership': (
            'kaori_correlated' if correlated else
            'kaori_marker_unverified' if (marked or ambiguous_marker) else 'external_observed'
        ),
        'kaori_grant_id': marker if correlated else None,
        'claimed_grant_marker': marker if marker and not correlated else None,
        'effective_permissions_verified': False,
    }


def latest_external_native_access_evidence(tenant_id: str) -> dict[str, Any] | None:
    event = (
        AuditEvent.query.filter_by(target_type=_TARGET, target_id=tenant_id)
        .order_by(AuditEvent.id.desc())
        .first()
    )
    return dict(event.metadata_json or {}) if event else None


def observe_external_native_access_committed(*, tenant_id: str, actor_user_id: int) -> dict[str, Any]:
    """Read only committed Tenant scope's current namespace RBAC and commit observation."""
    tenant = db.session.get(Tenant, tenant_id)
    if (
        tenant is None or tenant.provider_key != 'native_kubernetes'
        or tenant.reconciliation_authority != 'native_kubernetes'
        or tenant.provider_state != 'native' or tenant.lifecycle_status != 'ready'
    ):
        raise ValueError('Choose a healthy governed Native Kubernetes Tenant.')
    cluster = db.session.get(Cluster, tenant.cluster_id)
    if cluster is None:
        raise ValueError('Native Tenant cluster is missing.')

    records = (
        TenantNamespace.query.join(
            TenantEnvironment, TenantEnvironment.id == TenantNamespace.tenant_environment_id
        ).filter(
            TenantEnvironment.tenant_id == tenant.id,
            TenantNamespace.provisioning_status == 'ready',
            TenantNamespace.ownership_status.in_(['adopted', 'managed']),
        ).order_by(TenantNamespace.id.asc()).all()
    )
    if not records or len(records) > _MAX_NAMESPACES:
        raise ValueError('Native Tenant needs 1-30 governed Ready namespaces for bounded RBAC inspection.')
    if len({item.namespace for item in records}) != len(records):
        raise ValueError('Ambiguous duplicate Namespace governance generations; resolve before RBAC inspection.')

    grant_ids = {
        public_id for (public_id,) in db.session.query(TenantAccessGrant.public_id)
        .filter(TenantAccessGrant.tenant_id == tenant.id).all()
    }
    client = runtime_adapter.build_client(cluster)
    core = client.core_api()
    rbac = client.rbac_authorization_api()
    bindings: list[dict[str, Any]] = []
    observed_namespaces: list[dict[str, str]] = []
    for record in records:
        observed = core.read_namespace(record.namespace, _request_timeout=5)
        meta = getattr(observed, 'metadata', None)
        uid = str(getattr(meta, 'uid', '') or '').strip()
        version = str(getattr(meta, 'resource_version', '') or '').strip()
        if not uid or not version or (record.provider_reference and record.provider_reference != uid):
            raise ValueError(f'Namespace {record.namespace} provider UID/resourceVersion no longer matches.')
        observed_namespaces.append({'name': record.namespace, 'uid': uid, 'resource_version': version})

        remaining = _MAX_BINDINGS - len(bindings)
        listing = rbac.list_namespaced_role_binding(
            record.namespace, limit=remaining + 1, _request_timeout=5
        )
        items = getattr(listing, 'items', None)
        continuation = str(getattr(getattr(listing, 'metadata', None), '_continue', '') or '')
        if not isinstance(items, list) or len(items) > remaining or continuation:
            raise ValueError('Native Tenant RoleBinding inventory is incomplete or exceeds bounded limit.')
        for item in items:
            bindings.append(
                normalize_native_role_binding(item, namespace=record.namespace, grant_ids=grant_ids)
            )

    payload = {
        'provider': 'native_kubernetes',
        'tenant_id': tenant.id,
        'cluster_id': tenant.cluster_id,
        'namespaces': observed_namespaces,
        'bindings': bindings,
        'external_count': sum(x['ownership'] == 'external_observed' for x in bindings),
        'kaori_correlated_count': sum(x['ownership'] == 'kaori_correlated' for x in bindings),
        'unverified_marker_count': sum(x['ownership'] == 'kaori_marker_unverified' for x in bindings),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    evidence = {
        **payload,
        'status': 'review_required' if any(x['ownership'] != 'kaori_correlated' for x in bindings)
        else 'observed',
        'evidence_sha256': digest,
        'observed_at': datetime.now(UTC).isoformat(),
        'identity_import_performed': False,
        'rbac_mutation_performed': False,
        'effective_rbac_verified': False,
        'secret_material_persisted': False,
    }
    db.session.add(AuditEvent(
        actor_user_id=actor_user_id,
        target_type=_TARGET,
        target_id=tenant.id,
        action='tenant.external_native_access.observed',
        summary='Observed Native Namespace RBAC without changing provider resources or KAORI principals.',
        metadata_json=evidence,
    ))
    db.session.commit()
    return evidence
