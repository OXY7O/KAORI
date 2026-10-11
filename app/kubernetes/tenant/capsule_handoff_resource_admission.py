"""Fail-closed per-resource Capsule origin and handoff admissibility index (#1229).

Only exact committed provider inventory is classified. This is NOT a
Kubernetes admission or verification authority: labels, ownerReferences,
RBAC intent hashes and Kubernetes managedFields cannot independently prove
which authenticated controller created a resource. Never grant dry-run/live
PATCH from caller-supplied provenance claims.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import validate_capsule_handoff_scope
from app.kubernetes.tenant.capsule_handoff_controller_audit_claims import (
    correlate_capsule_controller_audit_claims,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

_SHA = re.compile(r'[0-9a-f]{64}\Z')
_RELATED = frozenset({'ResourceQuota', 'LimitRange', 'RoleBinding'})
_NO_TRANSFER = frozenset({
    'provider_cr_preservation_review_required',
    'preserve_cluster_scoped_quota',
    'preserve_foreign_provider_control',
    'preserve_existing_provider_namespace',
})
_TRANSFER_CANDIDATES = frozenset({
    'candidate_kaori_metadata_handoff_review',
    'explicit_kaori_metadata_handoff_review',
})


def _sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def assess_capsule_resource_handoff_scope(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    controller_audit_claims: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Index every Capsule/Namespace/quota/limit/RBAC identity, grant no rights.

    Namespaced objects require an independently authenticated Kubernetes
    origin chain and per-object successor handoff; merely matching hashes or
    KAORI labels does not prove controller provenance or accepted consent.
    """
    if (
        not isinstance(plan, Mapping) or not isinstance(related, Mapping)
        or plan.get('provider') != 'capsule'
        or not isinstance(plan.get('tenant_id'), str) or not plan['tenant_id']
        or not isinstance(plan.get('cluster_id'), str) or not plan['cluster_id']
        or not _sha(plan.get('plan_sha256'))
        or _plan_hash(dict(plan)) != plan['plan_sha256']
        or handoff_fingerprint(plan.get('handoff_components')) != plan.get('handoff_fingerprint')
    ):
        raise ValueError('Capsule per-resource review requires the exact SHA-bound plan.')
    cr, namespaces = validate_capsule_handoff_scope(plan['handoff_components'])
    if not all(_sha(cr.get(name)) for name in (
        'capsule_spec_sha256', 'capsule_related_resources_sha256',
        'capsule_shared_quota_sha256', 'capsule_rbac_lineage_sha256',
    )):
        raise ValueError('Capsule plan lacks full quota, RBAC and spec provenance digests.')
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    observed = related.get('resources')
    lineage = related.get('rbac_lineage')
    quota = related.get('global_quota')
    if (
        related.get('status') != 'read_only_related_inventory'
        or not isinstance(observed, list)
        or not isinstance(lineage, Mapping)
        or not isinstance(quota, Mapping)
        or lineage.get('status') != 'contract_correlated_controller_origin_unverified'
        or not _sha(lineage.get('lineage_sha256'))
        or lineage['lineage_sha256'] != cr['capsule_rbac_lineage_sha256']
        or lineage.get('controller_origin_verified') is not False
        or not isinstance(lineage.get('blockers'), list)
        or not isinstance(quota.get('blockers'), list)
        or quota.get('status') != 'observed_not_handoff_authorized'
        or not isinstance(related.get('blockers'), list)
    ):
        raise ValueError('Capsule per-resource review requires the complete unadmitted provider evidence.')
    ns_map = {row['name']: row for row in namespaces}
    related_map: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for obj in observed:
        if not isinstance(obj, Mapping):
            raise ValueError('Capsule per-resource evidence contains malformed related objects.')
        key = (obj.get('namespace'), obj.get('kind'), obj.get('name'))
        if key in related_map or key[1] not in _RELATED or key[0] not in ns_map:
            raise ValueError('Capsule per-resource origin scope is duplicate or foreign.')
        related_map[key] = obj
    results: list[dict[str, Any]] = []
    for item in worklist['items']:
        kind, name, namespace = item['kind'], item['name'], item['namespace']
        decision = item['decision']
        blockers: list[str] = []
        origin = 'provider_preserved'
        if kind == 'CapsuleTenant':
            if decision != 'provider_cr_preservation_review_required':
                raise ValueError('Capsule Tenant controller resource may not be transferred.')
            blockers.append('capsule_tenant_spec_and_owner_must_remain_provider_authoritative')
        elif kind == 'GlobalResourceQuota':
            if decision not in ('preserve_cluster_scoped_quota', 'operator_selector_investigation'):
                raise ValueError('Capsule cluster quota cannot enter metadata transfer.')
            blockers.append('cluster_scoped_quota_preservation_required')
            if decision == 'operator_selector_investigation':
                blockers.append('global_quota_selector_scope_unverified')
        elif kind == 'Namespace':
            source = ns_map[name]
            origin = source['ownership']
            if decision in _TRANSFER_CANDIDATES:
                if (
                    decision != 'candidate_kaori_metadata_handoff_review'
                    or source['ownership'] != 'kaori_marker_correlated'
                    or source['handoff'] != 'external_acceptance_required'
                    or source['uid'] != item['uid']
                    or source['resource_version'] != item['resource_version']
                ):
                    raise ValueError('Capsule Namespace metadata transfer is not exact-source bounded.')
                blockers.extend((
                    'namespace_kaori_marker_only_not_authenticated_origin',
                    'namespace_exact_metadata_only_successor_handoff_not_admitted',
                ))
            elif decision == 'operator_origin_investigation':
                blockers.append('namespace_ownership_unattributed_or_foreign')
            else:
                blockers.append('namespace_provider_preservation_not_transfer')
        elif kind in _RELATED:
            src = related_map.get((namespace, kind, name))
            if (
                not isinstance(src, Mapping)
                or src.get('uid') != item['uid']
                or src.get('resource_version') != item['resource_version']
                or not _sha(src.get('policy_sha256'))
                or not _sha(src.get('metadata_sha256'))
            ):
                raise ValueError('Capsule namespaced resource lacks exact UID/RV/policy/metadata evidence.')
            origin = src.get('origin')
            if decision in _TRANSFER_CANDIDATES:
                if decision != 'explicit_kaori_metadata_handoff_review' or origin != 'kaori_correlated':
                    raise ValueError('Capsule related-resource transfer has ambiguous ownership.')
                blockers.extend((
                    'kaori_label_correlation_not_authenticated_controller_provenance',
                    'resource_specific_metadata_only_successor_handoff_not_admitted',
                ))
                if kind == 'RoleBinding':
                    if (
                        not _sha(src.get('binding_contract_sha256'))
                        or not _sha(src.get('grant_scope_sha256'))
                        or lineage.get('contract_correlated') is not True
                        or lineage['blockers']
                    ):
                        blockers.append('rbac_intent_effective_binding_not_proven')
                    blockers.append('rbac_originating_controller_identity_not_authenticated')
                else:
                    blockers.append('allocation_policy_and_provider_quota_spec_must_be_preserved')
            elif decision == 'operator_origin_investigation':
                blockers.append('quota_limit_or_rbac_ownership_ambiguous')
            else:
                blockers.append('namespaced_foreign_policy_must_be_preserved')
        else:
            raise ValueError('Unrecognized Capsule resource kind in governance inventory.')
        results.append({
            'kind': kind, 'namespace': namespace, 'name': name,
            'uid': item['uid'], 'resource_version': item['resource_version'],
            'policy_sha256': item.get('policy_sha256'),
            'metadata_sha256': (
                related_map[(namespace, kind, name)].get('metadata_sha256')
                if kind in _RELATED else None
            ),
            'inventory_decision': decision,
            'observed_origin': origin,
            'provenance_status': (
                'source_correlated_not_controller_attested'
                if decision in _TRANSFER_CANDIDATES
                else 'preserve_or_manual_origin_review'
            ),
            'controller_identity_authenticated': False,
            'controller_origin_attested': False,
            'independent_resource_consent_verified': False,
            'metadata_only_handoff_admitted': False,
            'provider_spec_mutation_allowed': False,
            'provider_execution_admitted': False,
            'blockers': blockers,
        })
    if len(results) != worklist['item_count']:
        raise ValueError('Capsule per-resource investigation omitted provider objects.')
    audit = correlate_capsule_controller_audit_claims(
        tenant_id=plan['tenant_id'], cluster_id=plan['cluster_id'],
        resources=results,
        claims=[] if controller_audit_claims is None else controller_audit_claims,
    )
    for row in results:
        key = (row['namespace'], row['kind'], row['name'])
        claim = audit['claims_by_resource'].get(key)
        row['controller_audit_claim_sha256'] = claim
        row['controller_audit_claim_correlated'] = claim is not None
        if claim is not None:
            row['blockers'].append('controller_audit_claim_source_authentication_not_proven')
    candidates = [row for row in results if row['inventory_decision'] in _TRANSFER_CANDIDATES]
    unresolved = [
        row for row in results if row['inventory_decision'] not in _NO_TRANSFER
    ]
    return {
        'status': 'resource_specific_controller_provenance_unverified',
        'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'],
        'generation': plan.get('generation'),
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'rbac_lineage_sha256': lineage['lineage_sha256'],
        'resource_count': len(results),
        'source_candidate_count': len(candidates),
        'unresolved_origin_or_consent_count': len(unresolved),
        'resources': results,
        'resource_review_sha256': _digest(results),
        'controller_audit_claim_count': audit['claim_count'],
        'controller_audit_source_authenticated': False,
        'blockers': sorted(set(
            reason for row in results for reason in row['blockers']
        ) | set(related['blockers']) | set(quota['blockers']) | set(lineage['blockers'])),
        'controller_origin_verified': False,
        'resource_specific_handoff_admitted': False,
        'dry_run_admitted': False,
        'provider_execution_admitted': False,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'resume_authorized': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
