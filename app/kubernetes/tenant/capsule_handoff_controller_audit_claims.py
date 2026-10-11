"""Untrusted Kubernetes apiserver audit-origin claim correlation for Capsule #1229.

A well-formed audit record is NOT authenticated evidence of which controller
created a RoleBinding, quota or limit. Only a separately validated apiserver
audit collection and principal trust root may elevate source authentication;
this pure correlation never authorizes provider mutation or Release.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_MAX_CLAIMS = 300
_FIELDS = frozenset({
    'source', 'audit_id', 'event_at', 'stage', 'verb',
    'cluster_id', 'tenant_id', 'kind', 'namespace', 'name',
    'uid', 'resource_version', 'response_code',
    'controller_principal_sha256', 'policy_sha256', 'metadata_sha256',
})
_KINDS = frozenset({'Namespace', 'ResourceQuota', 'LimitRange', 'RoleBinding'})


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def correlate_capsule_controller_audit_claims(
    *, tenant_id: str, cluster_id: str,
    resources: list[dict[str, Any]], claims: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind asserted AuditEvent metadata to exact resource identity/digests.

    NEVER trust source/actor fields merely because the caller supplied them.
    No raw principal, RBAC subject, credential or audit object is returned.
    """
    if (
        not isinstance(tenant_id, str) or not tenant_id
        or not isinstance(cluster_id, str) or not cluster_id
        or not isinstance(resources, list)
        or not isinstance(claims, list) or len(claims) > _MAX_CLAIMS
    ):
        raise ValueError('Capsule audit-origin claims require bounded canonical scope.')
    candidate_keys: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in resources:
        if not isinstance(row, Mapping):
            raise ValueError('Capsule controller audit target is malformed.')
        if row.get('kind') not in _KINDS:
            continue
        if row.get('inventory_decision') not in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        ):
            continue
        key = (row['namespace'], row['kind'], row['name'])
        if key in candidate_keys:
            raise ValueError('Duplicate Capsule audit proof target.')
        candidate_keys[key] = row
    results: dict[tuple[str, str, str], str] = {}
    seen_audit_ids: set[str] = set()
    for record in claims:
        if not isinstance(record, Mapping) or set(record) != _FIELDS:
            raise ValueError('Capsule audit claim contains unknown or missing fields.')
        key = (record['namespace'], record['kind'], record['name'])
        source = candidate_keys.get(key)
        try:
            audit_id = UUID(str(record['audit_id']))
            at = datetime.fromisoformat(record['event_at'])
        except (TypeError, ValueError, AttributeError, KeyError) as exc:
            raise ValueError('Capsule controller audit identity/time is invalid.') from exc
        if (
            source is None or key in results
            or str(audit_id) != record['audit_id']
            or record['audit_id'] in seen_audit_ids
            or at.tzinfo is None or at.utcoffset() is None
            or record['source'] != 'kubernetes_apiserver_audit'
            or record['stage'] != 'ResponseComplete'
            or record['verb'] not in ('create', 'patch', 'update')
            or type(record['response_code']) is not int
            or record['response_code'] not in (200, 201)
            or record['tenant_id'] != tenant_id
            or record['cluster_id'] != cluster_id
            or record['uid'] != source['uid']
            or record['resource_version'] != source['resource_version']
            or not _is_sha(record['controller_principal_sha256'])
            or record['policy_sha256'] != source.get('policy_sha256')
            or record['metadata_sha256'] != source.get('metadata_sha256')
        ):
            raise ValueError(
                'Capsule audit claim does not match an exact KAORI resource scope.'
            )
        seen_audit_ids.add(record['audit_id'])
        results[key] = _digest(dict(record))
    return {
        'status': 'caller_supplied_apiserver_audit_claims_correlated_not_authenticated',
        'claims_by_resource': results,
        'claim_count': len(results),
        'audit_source_authenticated': False,
        'controller_principal_trust_root_verified': False,
        'controller_origin_attested': False,
        'resource_specific_handoff_admitted': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
    }
