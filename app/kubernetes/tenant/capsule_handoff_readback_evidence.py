"""Read-only candidate Capsule provider read-back comparison (#1229).

Takes separately acquired Kubernetes observations; never fetches, PATCHes,
persists, or proves that caller supplied fresh authenticated read-back. This
is NOT independent provider verification nor an admitted Release receipt.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import (
    _identity,
    classify_capsule_related_metadata_readback,
    validate_capsule_handoff_scope,
    verify_capsule_cr_preserved,
)
from app.kubernetes.tenant.capsule_handoff_recovery import classify_capsule_namespace_handoff
from app.kubernetes.tenant.capsule_handoff_related_inventory import (
    _digest,
    classify_capsule_related_resource,
)
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

_MAX_RESOURCES = 300


def _fingerprints(
    related: Mapping[str, Any],
    *,
    names: set[str],
) -> tuple[str, str]:
    """Recompute complete candidate LIST digests, rejecting missing scopes."""
    rows, lists = related.get('resources'), related.get('list_snapshots')
    quota = related.get('global_quota')
    if (
        not isinstance(rows, list)
        or len(rows) > _MAX_RESOURCES
        or not isinstance(lists, list)
        or not isinstance(quota, Mapping)
        or not isinstance(quota.get('resources'), list)
        or quota.get('served_version') not in ('v1beta1', 'v1beta2')
        or not isinstance(quota.get('list_resource_version'), str)
        or not quota['list_resource_version']
    ):
        raise ValueError('Capsule read-back provider LIST coverage is malformed.')
    expected_lists = {(ns, kind) for ns in names for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')}
    observed_lists: list[tuple[str, str]] = []
    counts: dict[tuple[str, str], int] = {}
    for item in lists:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule read-back has malformed provider LIST metadata.')
        ns, kind = item.get('namespace'), item.get('kind')
        rv, count = item.get('list_resource_version'), item.get('count')
        if (
            not isinstance(ns, str)
            or not isinstance(kind, str)
            or not isinstance(rv, str)
            or not rv
            or type(count) is not int
            or not 0 <= count <= 100
        ):
            raise ValueError('Capsule read-back has incomplete LIST scope/revisions.')
        observed_lists.append((ns, kind))
        counts[(ns, kind)] = count
    if (
        len(observed_lists) != len(expected_lists)
        or len(set(observed_lists)) != len(observed_lists)
        or set(observed_lists) != expected_lists
    ):
        raise ValueError('Capsule read-back omitted or duplicated namespaced LIST coverage.')
    seen_resources: set[tuple[str, str, str]] = set()
    observed_counts: dict[tuple[str, str], int] = {}
    for item in rows:
        if not isinstance(item, Mapping):
            raise ValueError('Capsule read-back resource record is malformed.')
        ns, kind, name = item.get('namespace'), item.get('kind'), item.get('name')
        uid, rv = item.get('uid'), item.get('resource_version')
        if (
            not all(isinstance(v, str) and v for v in (ns, kind, name, uid, rv))
            or (ns, kind) not in expected_lists
            or (ns, kind, name) in seen_resources
        ):
            raise ValueError('Capsule read-back related resource identity is not unique and scoped.')
        seen_resources.add((ns, kind, name))
        observed_counts[(ns, kind)] = observed_counts.get((ns, kind), 0) + 1
    if any(observed_counts.get(key, 0) != count for key, count in counts.items()):
        raise ValueError('Capsule read-back listed resource counts are inconsistent.')
    if len(quota['resources']) > 100:
        raise ValueError('Capsule cluster quota read-back exceeds admitted list bound.')
    related_sha = _digest({'resources': rows, 'lists': lists})
    quota_sha = _digest(
        {
            'api_version': quota['served_version'],
            'list_resource_version': quota['list_resource_version'],
            'resources': quota['resources'],
        }
    )
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


def _review_related_scope(
    *,
    plan: Mapping[str, Any],
    worklist: Mapping[str, Any],
    source_related: Mapping[str, Any],
    current_related: Mapping[str, Any],
    evidence: Mapping[tuple[str, str, str], Mapping[str, Any]] | None,
) -> tuple[list[dict[str, str]], int, int, list[str]]:
    """Accept only explainable per-object metadata deltas across complete LISTs.

    Raw caller-supplied before/after bodies and label consent are NOT
    authenticated provider snapshots or human authority.
    """
    source = {(r['namespace'], r['kind'], r['name']): r for r in source_related['resources']}
    current = {(r['namespace'], r['kind'], r['name']): r for r in current_related['resources']}
    candidates = {
        (r['namespace'], r['kind'], r['name']): r
        for r in worklist['items']
        if r['decision'] == 'explicit_kaori_metadata_handoff_review'
    }
    if evidence is not None and (
        not isinstance(evidence, Mapping)
        or set(evidence) != set(candidates)
        or any(
            not isinstance(row, Mapping) or set(row) != {'before', 'current', 'approved_label_keys'}
            for row in evidence.values()
        )
    ):
        raise ValueError('Capsule related raw handoff evidence must cover exactly all candidates.')
    blockers: list[str] = []
    if set(source) != set(current):
        blockers.append('related_resource_add_delete_or_scope_drift')
    original_lists = {(row['namespace'], row['kind']): row for row in source_related['list_snapshots']}
    new_lists = {(row['namespace'], row['kind']): row for row in current_related['list_snapshots']}
    capsule = next(row for row in plan['handoff_components'] if row['kind'] == 'CapsuleTenant')
    transferred_scopes: set[tuple[str, str]] = set()
    observations: list[dict[str, str]] = []
    transferred = pending = 0
    for key, work_item in candidates.items():
        original = source.get(key)
        observed = current.get(key)
        state = 'ambiguous_recovery_required'
        if original is None or observed is None:
            blockers.append('related_transfer_target_missing_or_replaced')
        elif evidence is None:
            if original == observed:
                state = 'pending_provider_transfer'
            else:
                blockers.append('related_kaori_control_recovery_unverified')
        else:
            entry = evidence[key]
            try:
                if any(
                    original.get(field) != work_item.get(field)
                    for field in (
                        'kind',
                        'namespace',
                        'name',
                        'uid',
                        'resource_version',
                        'policy_sha256',
                    )
                ):
                    raise ValueError('Original Capsule LIST differs from approved worklist.')
                projection, problems = classify_capsule_related_resource(
                    resource=entry['current'],
                    kind=key[1],
                    namespace=key[0],
                    tenant_id=plan['tenant_id'],
                    capsule_name=capsule['name'],
                    capsule_uid=capsule['uid'],
                )
                if projection != observed:
                    raise ValueError('Capsule current LIST disagrees with raw object.')
                outcome = classify_capsule_related_metadata_readback(
                    record=original,
                    before=entry['before'],
                    current=entry['current'],
                    kind=key[1],
                    namespace=key[0],
                    tenant_id=plan['tenant_id'],
                    capsule_name=capsule['name'],
                    capsule_uid=capsule['uid'],
                    successor_owner=str(plan.get('successor_owner') or ''),
                    approved_label_keys=entry['approved_label_keys'],
                )
                state = outcome['state']
                if state == 'provider_markers_transferred' and problems:
                    raise ValueError('Capsule transferred control retains ambiguous ownership.')
            except (TypeError, ValueError, KeyError, AttributeError):
                state = 'ambiguous_recovery_required'
                blockers.append('related_transfer_identity_policy_or_metadata_drift')
        if state == 'provider_markers_transferred':
            transferred += 1
            transferred_scopes.add((key[0], key[1]))
        elif state == 'pending_provider_transfer':
            pending += 1
        observations.append(
            {
                'kind': key[1],
                'namespace': key[0],
                'name': key[2],
                'uid': work_item['uid'],
                'state': state,
            }
        )
    for key, original in source.items():
        if key not in candidates and original != current.get(key):
            blockers.append('related_foreign_or_unadmitted_control_drift')
    for scope, original in original_lists.items():
        after = new_lists[scope]
        # Only a version bump may be explained by a permitted transfer;
        # additional or changed LIST envelope fields are never exempt.
        if (
            set(original) != {'namespace', 'kind', 'list_resource_version', 'count'}
            or set(after) != set(original)
            or any(after[field] != original[field] for field in ('namespace', 'kind', 'count'))
        ):
            blockers.append('related_list_schema_scope_or_count_changed')
        list_changed = after['list_resource_version'] != original['list_resource_version']
        if after['count'] != original['count']:
            blockers.append('related_list_resource_count_changed')
        if list_changed and scope not in transferred_scopes:
            blockers.append('namespaced_list_revision_drift')
        if not list_changed and scope in transferred_scopes:
            blockers.append('related_transfer_list_revision_not_observed')
    observations.sort(key=lambda x: (x['namespace'], x['kind'], x['name']))
    return observations, transferred, pending, blockers


def inspect_capsule_readback_candidate(
    *,
    plan: Mapping[str, Any],
    source_related: Mapping[str, Any],
    current_related: Mapping[str, Any],
    current_capsule_cr: Any,
    current_namespaces: Mapping[str, Any],
    namespace_baselines: list[dict[str, Any]],
    tenant_id: str,
    related_transfer_evidence: (Mapping[tuple[str, str, str], Mapping[str, Any]] | None) = None,
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
        or not isinstance(tenant_id, str)
        or not tenant_id
        or plan.get('tenant_id') != tenant_id
    ):
        raise ValueError('Capsule read-back requires canonical provider and Tenant scope.')
    cr, namespaces = validate_capsule_handoff_scope(plan.get('handoff_components'))
    if (
        plan.get('provider') != 'capsule'
        or not isinstance(plan.get('plan_sha256'), str)
        or _plan_hash(dict(plan)) != plan['plan_sha256']
        or handoff_fingerprint(plan['handoff_components']) != plan.get('handoff_fingerprint')
    ):
        raise ValueError('Capsule read-back plan SHA or handoff fingerprint is invalid.')
    worklist = build_capsule_handoff_worklist(plan=plan, related=source_related)
    # The plan also pins the RBAC intent/lineage scope, not merely the
    # quota/limit/RoleBinding LIST hash. Without this comparison a caller
    # could replace the source lineage, recompute unrelated list digests,
    # and obtain a structurally complete but misleading G3 receipt.
    lineage = source_related.get('rbac_lineage')
    if (
        not isinstance(lineage, Mapping)
        or lineage.get('status') != 'contract_correlated_controller_origin_unverified'
        or lineage.get('lineage_sha256') != cr.get('capsule_rbac_lineage_sha256')
        or lineage.get('controller_origin_verified') is not False
        or not isinstance(lineage.get('blockers'), list)
        or source_related.get('status') != 'read_only_related_inventory'
        or not isinstance(source_related.get('blockers'), list)
        or source_related.get('global_quota', {}).get('status') != 'observed_not_handoff_authorized'
        or not isinstance(source_related['global_quota'].get('blockers'), list)
    ):
        raise ValueError('Capsule G3 source RBAC lineage or inventory posture is not plan-bound.')
    scoped_names = {row['name'] for row in namespaces}
    base_related_sha, base_quota_sha = _fingerprints(source_related, names=scoped_names)
    if base_related_sha != cr.get('capsule_related_resources_sha256') or base_quota_sha != cr.get(
        'capsule_shared_quota_sha256'
    ):
        raise ValueError('Capsule read-back original scope is no longer SHA-bound.')
    current_related_sha, current_quota_sha = _fingerprints(
        current_related,
        names=scoped_names,
    )
    ns_by_name = {item['name']: item for item in namespaces}
    if set(current_namespaces) != set(ns_by_name):
        raise ValueError('Capsule read-back Namespace set is partial or includes foreign objects.')
    required_baselines = {item['name'] for item in namespaces if item['handoff'] == 'external_acceptance_required'}
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
    # The classifier legitimately reports a KAORI-managed related object as
    # requiring handoff. Only those known candidate warnings may accompany
    # an otherwise coherent source/current observation; arbitrary collector,
    # foreign-owner or controller/RBAC findings must not disappear behind a
    # valid source/current resource_sha256.
    allowed_handoff_warnings = {
        (
            f'Capsule {item["kind"]}/{item["namespace"]}/{item["name"]} '
            'retains KAORI provider controls requiring separately admitted handoff.'
        )
        for item in worklist['items']
        if item['decision'] == 'explicit_kaori_metadata_handoff_review'
    }
    for snapshot in (source_related, current_related):
        evidence = snapshot.get('blockers')
        quota_evidence = snapshot.get('global_quota')
        lineage_evidence = snapshot.get('rbac_lineage')
        if (
            snapshot.get('status') != 'read_only_related_inventory'
            or not isinstance(evidence, list)
            or not isinstance(quota_evidence, Mapping)
            or quota_evidence.get('status') != 'observed_not_handoff_authorized'
            or not isinstance(quota_evidence.get('blockers'), list)
            or not isinstance(lineage_evidence, Mapping)
            or lineage_evidence.get('status') != 'contract_correlated_controller_origin_unverified'
            or lineage_evidence.get('controller_origin_verified') is not False
            or not isinstance(lineage_evidence.get('blockers'), list)
            or any(not isinstance(item, str) for item in evidence)
            or any(not isinstance(item, str) for item in quota_evidence['blockers'])
            or any(not isinstance(item, str) for item in lineage_evidence['blockers'])
        ):
            blockers.append('related_inventory_provenance_or_coverage_unverified')
            continue
        if any(warning not in allowed_handoff_warnings for warning in evidence):
            blockers.append('related_inventory_has_unresolved_provider_findings')
        if quota_evidence['blockers']:
            blockers.append('global_quota_has_unresolved_provider_findings')
        if lineage_evidence['blockers']:
            blockers.append('rbac_lineage_has_unresolved_provider_findings')
    try:
        cr_observation = verify_capsule_cr_preserved(cr, current_capsule_cr)
    except (TypeError, ValueError, KeyError, AttributeError):
        blockers.append('capsule_cr_provider_spec_or_identity_drift')
        cr_observation = None
    related_rows, related_transferred, related_pending, related_blockers = _review_related_scope(
        plan=plan,
        worklist=worklist,
        source_related=source_related,
        current_related=current_related,
        evidence=related_transfer_evidence,
    )
    blockers.extend(related_blockers)
    # An original KAORI handoff warning can remain on a still-pending
    # resource. It cannot remain on an allegedly transferred current object:
    # this would contradict the current canonical controller inventory.
    pending_kaori_warnings = {
        (
            f'Capsule {item["kind"]}/{item["namespace"]}/{item["name"]} '
            'retains KAORI provider controls requiring separately admitted handoff.'
        )
        for item in related_rows
        if item['state'] == 'pending_provider_transfer'
    }
    current_findings = current_related.get('blockers')
    if isinstance(current_findings, list) and any(
        warning in allowed_handoff_warnings and warning not in pending_kaori_warnings
        for warning in current_findings
        if isinstance(warning, str)
    ):
        blockers.append('related_current_handoff_finding_contradicts_readback')
    if current_related_sha != base_related_sha and related_blockers:
        blockers.append('namespaced_provider_object_or_list_changed')
    if current_quota_sha != base_quota_sha:
        blockers.append('cluster_global_quota_or_list_changed')
    # The per-object comparison above accepts only explainable marker
    # transfers; foreign/unapproved policy and LIST drift still fails.
    if source_related.get('global_quota') != current_related.get('global_quota'):
        blockers.append('global_quota_evidence_drift')
    if source_related.get('rbac_lineage') != current_related.get('rbac_lineage'):
        blockers.append('rbac_intent_effective_lineage_drift')

    rows: list[dict[str, str]] = []
    for namespace in namespaces:
        name = namespace['name']
        obj = current_namespaces[name]
        observed_name, observed_uid, observed_rv = _identity(obj)
        if (observed_name, observed_uid) != (name, namespace['uid']) or not observed_rv:
            blockers.append('namespace_uid_or_identity_drift')
            rows.append(
                {
                    'name': name,
                    'uid': str(observed_uid),
                    'state': 'identity_drift',
                }
            )
            continue
        if name not in baseline_by_name:
            # Observation-only namespace is not a transferable resource.
            if observed_rv != namespace['resource_version']:
                blockers.append('observed_foreign_namespace_rv_drift')
            # Without full original metadata/spec baseline we cannot assert
            # provider preservation merely from matching UID/RV.
            rows.append(
                {
                    'name': name,
                    'uid': observed_uid,
                    'state': 'observe_only_preservation_unproven',
                }
            )
            continue
        try:
            classified = classify_capsule_namespace_handoff(
                baseline=baseline_by_name[name],
                current=obj,
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
    expected_count = len(required_baselines) + len(related_rows)
    transferred += related_transferred
    pending += related_pending
    unknown = expected_count - transferred - pending
    if unknown:
        blockers.append('incomplete_transfer_candidate_readback_proof')
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
        'related_resource_observations': related_rows,
        'related_transfer_candidate_count': len(related_rows),
        'source_namespaced_sha256': base_related_sha,
        'candidate_namespaced_sha256': current_related_sha,
        'source_global_quota_sha256': base_quota_sha,
        'candidate_global_quota_sha256': current_quota_sha,
        'expected_count': expected_count,
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
