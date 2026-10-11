"""Pure, non-executable Capsule Release handoff worklist (#1229).

This is an operator investigation index, not a provider mutation plan.
No credential, RBAC subject, mutable provider body, or PATCH is persisted.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import validate_capsule_handoff_scope
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

_MAX_RELATED = 300
_MAX_GLOBAL = 100


def build_capsule_handoff_worklist(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify source work, including foreign resources, before provider auth."""
    if not isinstance(plan, Mapping) or not isinstance(related, Mapping):
        raise ValueError('An exact Capsule plan and correlated related inventory are required.')
    cr, namespaces = validate_capsule_handoff_scope(plan.get('handoff_components'))
    rows = related.get('resources')
    quota = related.get('global_quota')
    if (
        not isinstance(rows, list) or len(rows) > _MAX_RELATED
        or not isinstance(quota, Mapping)
        or not isinstance(quota.get('resources'), list)
        or len(quota['resources']) > _MAX_GLOBAL
        or related.get('resource_sha256') != cr.get('capsule_related_resources_sha256')
        or quota.get('scope_sha256') != cr.get('capsule_shared_quota_sha256')
    ):
        raise ValueError('Capsule worklist lacks SHA-bound complete authoritative inventory.')
    names = {row['name'] for row in namespaces}
    tasks: list[dict[str, str]] = []
    identities: set[tuple[str, str, str]] = set()

    def append(
        *, kind: object, namespace: object, name: object,
        uid: object, rv: object, action: str, evidence_sha256: object = None,
    ) -> None:
        if (
            not all(isinstance(x, str) and x for x in (kind, name, uid, rv))
            or not isinstance(namespace, str)
            or (namespace and namespace not in names)
        ):
            raise ValueError('Capsule worklist contains an invalid provider object.')
        key = (namespace, kind, name)
        if key in identities:
            raise ValueError('Capsule worklist contains duplicate provider targets.')
        identities.add(key)
        result = {
            'kind': kind, 'namespace': namespace, 'name': name,
            'uid': uid, 'resource_version': rv, 'decision': action,
        }
        if evidence_sha256 is not None:
            if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
                raise ValueError('Capsule worklist lacks exact resource policy evidence.')
            result['policy_sha256'] = evidence_sha256
        tasks.append(result)

    append(
        kind='CapsuleTenant', namespace='', name=cr['name'],
        uid=cr['uid'], rv=cr['resource_version'],
        action='provider_cr_preservation_review_required',
        evidence_sha256=cr['capsule_spec_sha256'],
    )
    for ns in namespaces:
        append(
            kind='Namespace', namespace='', name=ns['name'],
            uid=ns['uid'], rv=ns['resource_version'],
            action=(
                'candidate_kaori_metadata_handoff_review'
                if ns['handoff'] == 'external_acceptance_required'
                else 'preserve_existing_provider_namespace'
            ),
        )
    for obj in rows:
        if (
            not isinstance(obj, Mapping)
            or obj.get('kind') not in ('ResourceQuota', 'LimitRange', 'RoleBinding')
            or obj.get('namespace') not in names
        ):
            raise ValueError('Unscoped or unsupported Capsule governance object.')
        origin = obj.get('origin')
        if origin == 'kaori_correlated':
            action = 'explicit_kaori_metadata_handoff_review'
        elif origin in ('capsule_provider', 'foreign_preserved'):
            action = 'preserve_foreign_provider_control'
        elif origin in ('ambiguous_kaori', 'unattributed'):
            action = 'operator_origin_investigation'
        else:
            raise ValueError('Capsule governance origin is unclassified.')
        append(
            kind=obj['kind'], namespace=obj['namespace'], name=obj.get('name'),
            uid=obj.get('uid'), rv=obj.get('resource_version'), action=action,
            evidence_sha256=obj.get('policy_sha256'),
        )
    for obj in quota['resources']:
        if not isinstance(obj, Mapping) or obj.get('kind') != 'GlobalResourceQuota':
            raise ValueError('Capsule shared quota worklist is incomplete.')
        scope = obj.get('scope')
        if scope == 'unverified_selector':
            action = 'operator_selector_investigation'
        elif scope in ('direct_tenant_selector', 'other_tenant_selector'):
            action = 'preserve_cluster_scoped_quota'
        else:
            raise ValueError('Capsule global quota scope is unknown.')
        append(
            kind='GlobalResourceQuota', namespace='', name=obj.get('name'),
            uid=obj.get('uid'), rv=obj.get('resource_version'), action=action,
            evidence_sha256=obj.get('policy_sha256'),
        )
    tasks.sort(key=lambda item: (item['namespace'], item['kind'], item['name']))
    manual = sum(
        item['decision'] in {
            'provider_cr_preservation_review_required',
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
            'operator_origin_investigation', 'operator_selector_investigation',
        }
        for item in tasks
    )
    return {
        'status': 'operator_review_only',
        'plan_sha256': plan.get('plan_sha256'),
        'items': tasks,
        'item_count': len(tasks),
        'manual_review_count': manual,
        'inventory_sha256': _digest(tasks),
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'dry_run_admitted': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
    }
