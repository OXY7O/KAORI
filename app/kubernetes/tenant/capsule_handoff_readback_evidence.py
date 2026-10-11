"""Read-only candidate Capsule provider read-back comparison (#1229).

Takes separately acquired Kubernetes observations; never fetches, PATCHes,
persists, or proves that caller supplied fresh authenticated read-back. This
is NOT independent provider verification nor an admitted Release receipt.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity, verify_capsule_cr_preserved, validate_capsule_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_recovery import classify_capsule_namespace_handoff
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist

_MAX_RESOURCES = 300


def _fingerprints(related: Mapping[str, Any]) -> tuple[str, str]:
    """Recompute candidate LIST digests; never trust caller-provided hashes."""
    rows, lists = related.get('resources'), related.get('list_snapshots')
    quota = related.get('global_quota')
    if (
        not isinstance(rows, list) or len(rows) > _MAX_RESOURCES
        or not isinstance(lists, list) or not isinstance(quota, Mapping)
        or not isinstance(quota.get('resources'), list)
        or quota.get('served_version') not in ('v1beta1', 'v1beta2')
        or not isinstance(quota.get('list_resource_version'), str)
        or not quota['list_resource_version']
    ):
        raise ValueError('Capsule read-back provider LIST coverage is malformed.')
    related_sha = _digest({'resources': rows, 'lists': lists})
    quota_sha = _digest({
        'api_version': quota['served_version'],
        'list_resource_version': quota['list_resource_version'],
        'resources': quota['resources'],
    })
    if (
        related_sha != related.get('resource_sha256')
        or quota_sha != quota.get('scope_sha256')
        or type(related.get('resource_count')) is not int
        or related['resource_count'] != len(rows)
        or type(quota.get('count')) is not int
        or quota['count'] != len(quota['resources'])
    ):
        raise ValueError('Capsule read-back LIST digests or object counts are inconsistent.')
    return related_sha, quota_sha


def inspect_capsule_readback_candidate(
    *, plan: Mapping[str, Any], source_related: Mapping[str, Any],
    current_related: Mapping[str, Any], current_capsule_cr: Any,
    current_namespaces: Mapping[str, Any],
    namespace_baselines: list[dict[str, Any]], tenant_id: str,
) -> dict[str, Any]:
    """Compare full exact-scope provider snapshots without asserting execution.

    Provider LIST provenance, fresh X.509 authentication, and any successful
    mutation must be established by a separately reviewed, guarded service.
    """
    if (
        not isinstance(plan, Mapping)
        or not isinstance(source_related, Mapping)
        or not isinstance(current_related, Mapping)
        or not isinstance(current_namespaces, Mapping)
        or not isinstance(namespace_baselines, list)
        or not isinstance(tenant_id, str) or not tenant_id
        or plan.get('tenant_id') != tenant_id
    ):
        raise ValueError('Capsule read-back requires canonical provider and Tenant scope.')
    cr, namespaces = validate_capsule_handoff_scope(plan.get('handoff_components'))
    worklist = build_capsule_handoff_worklist(plan=plan, related=source_related)
    base_related_sha, base_quota_sha = _fingerprints(source_related)
    if (
        base_related_sha != cr.get('capsule_related_resources_sha256')
        or base_quota_sha != cr.get('capsule_shared_quota_sha256')
    ):
        raise ValueError('Capsule read-back original scope is no longer SHA-bound.')
    current_related_sha, current_quota_sha = _fingerprints(current_related)
    ns_by_name = {item['name']: item for item in namespaces}
    if set(current_namespaces) != set(ns_by_name):
        raise ValueError('Capsule read-back Namespace set is partial or includes foreign objects.')
    required_baselines = {
        item['name'] for item in namespaces
        if item['handoff'] == 'external_acceptance_required'
    }
    baseline_by_name: dict[str, dict[str, Any]] = {}
    for row in namespace_baselines:
        if not isinstance(row, Mapping) or not isinstance(row.get('name'), str):
            raise ValueError('Capsule read-back Namespace baseline is malformed.')
        if row['name'] in baseline_by_name:
            raise ValueError('Capsule read-back Namespace baseline identity was duplicated.')
        baseline_by_name[row['name']] = dict(row)
    if set(baseline_by_name) != required_baselines:
        raise ValueError('Capsule read-back Namespace baseline coverage is not exact.')

    blockers: list[str] = []
    try:
        cr_observation = verify_capsule_cr_preserved(cr, current_capsule_cr)
    except (TypeError, ValueError, KeyError, AttributeError):
        blockers.append('capsule_cr_provider_spec_or_identity_drift')
        cr_observation = None
    if current_related_sha != base_related_sha:
        blockers.append('namespaced_provider_object_or_list_changed')
    if current_quota_sha != base_quota_sha:
        blockers.append('cluster_global_quota_or_list_changed')
    # Full inventory records are required: a forged top-level digest or a
    # dropped row must not look like read-back.
    if source_related.get('resources') != current_related.get('resources'):
        blockers.append('namespaced_resource_identity_policy_or_metadata_drift')
    if source_related.get('list_snapshots') != current_related.get('list_snapshots'):
        blockers.append('namespaced_list_revision_drift')
    if source_related.get('global_quota') != current_related.get('global_quota'):
        blockers.append('global_quota_evidence_drift')
    if source_related.get('rbac_lineage') != current_related.get('rbac_lineage'):
        blockers.append('rbac_intent_effective_lineage_drift')

    rows: list[dict[str, str]] = []
    for namespace in namespaces:
        name = namespace['name']
        obj = current_namespaces[name]
        observed_name, observed_uid, observed_rv = _identity(obj)
        if (
            (observed_name, observed_uid) != (name, namespace['uid'])
            or not observed_rv
        ):
            blockers.append('namespace_uid_or_identity_drift')
            rows.append({
                'name': name, 'uid': str(observed_uid),
                'state': 'identity_drift',
            })
            continue
        if name not in baseline_by_name:
            # Observation-only namespace is not a transferable resource.
            if observed_rv != namespace['resource_version']:
                blockers.append('observed_foreign_namespace_rv_drift')
            # Without full original metadata/spec baseline we cannot assert
            # provider preservation merely from matching UID/RV.
            rows.append({
                'name': name, 'uid': observed_uid,
                'state': 'observe_only_preservation_unproven',
            })
            continue
        try:
            classified = classify_capsule_namespace_handoff(
                baseline=baseline_by_name[name], current=obj,
                tenant_id=tenant_id,
                successor_owner=str(plan.get('successor_owner') or ''),
            )
            state = classified['state']
        except (TypeError, ValueError, KeyError, AttributeError):
            blockers.append('namespace_ownership_or_preservation_drift')
            state = 'ambiguous_recovery_required'
        rows.append({'name': name, 'uid': observed_uid, 'state': state})
    rows.sort(key=lambda x: x['name'])
    transferred = sum(r['state'] == 'provider_markers_transferred' for r in rows)
    pending = sum(r['state'] == 'pending_provider_transfer' for r in rows)
    unknown = len(rows) - transferred - pending
    if unknown:
        blockers.append('incomplete_namespace_readback_proof')
    # Even an exact all-transferred status cannot prove proper admission,
    # independent actor authority, controller provenance or successor consent.
    blockers.append('capsule_controller_provenance_unverified')
    blockers.append('provider_execution_authority_unverified')
    receipt = {
        'plan_sha256': plan.get('plan_sha256'),
        'handoff_fingerprint': plan.get('handoff_fingerprint'),
        'worklist_sha256': worklist['inventory_sha256'],
        'capsule_cr_observed': cr_observation is not None,
        'namespace_observations': rows,
        'source_namespaced_sha256': base_related_sha,
        'candidate_namespaced_sha256': current_related_sha,
        'source_global_quota_sha256': base_quota_sha,
        'candidate_global_quota_sha256': current_quota_sha,
        'expected_count': len(required_baselines),
        'observed_count': transferred + pending,
        'pending_count': pending,
        'transferred_count': transferred,
        'ambiguous_count': unknown,
        'blockers': sorted(set(blockers)),
    }
    return {
        'status': 'readback_candidate_recovery_review_required',
        'readback_sha256': _digest(receipt),
        **receipt,
        'provider_snapshot_authenticity_verified': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'resume_authorized': False,
        'auto_retry_authorized': False,
        'provider_mutation_performed': False,
        'secret_material_persisted': False,
    }
