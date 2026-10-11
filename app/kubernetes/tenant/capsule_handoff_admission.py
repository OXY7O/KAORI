"""Fail-closed Capsule Release dry-run admission assessment (#1229).

Pure committed-evidence classifier. It never calls Kubernetes, writes audit
rows, patches a provider resource, grants retry, or changes Released status.

The consumer MUST independently reload current records and perform a fresh
authenticated provider SSR/SAR + preflight. A persisted receipt or a label is
not a substitute for controller provenance or live Kubernetes authority.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_contract import validate_capsule_handoff_scope
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.capsule_platform_admin_authority import _capsule_admin_scope
from app.kubernetes.tenant.release_handoff_approval import (
    _REQUIRED_DEPENDENCIES, _checked_recently, _plan_hash,
)
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

_SHA256 = re.compile(r'[a-f0-9]{64}\Z')


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _identity(obj: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(obj.get('namespace') or ''), str(obj.get('kind') or ''),
        str(obj.get('name') or ''), str(obj.get('uid') or ''),
    )


def _safe_plan_inventory(plan: Mapping[str, Any]) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    components = plan.get('handoff_components')
    cr, namespaces = validate_capsule_handoff_scope(components)
    if not all(
        _sha(cr.get(field))
        for field in (
            'capsule_spec_sha256', 'capsule_related_resources_sha256',
            'capsule_shared_quota_sha256', 'capsule_rbac_lineage_sha256',
        )
    ):
        raise ValueError('Capsule approved plan lacks complete bound provider digests.')
    if not isinstance(cr.get('capsule_related_resources_count'), str):
        raise ValueError('Capsule related resource count is missing from approved plan.')
    if not str(cr['capsule_related_resources_count']).isdigit():
        raise ValueError('Capsule related resource count is invalid.')
    return cr, namespaces


def _inspect_related(
    *, snapshot: Mapping[str, Any], cr: Mapping[str, Any],
    namespaces: list[dict[str, Any]],
) -> list[str]:
    """Check structural completeness; never promote correlated origins to proof."""
    reasons: list[str] = []
    related = snapshot.get('capsule_related_inventory')
    if not isinstance(related, Mapping):
        return ['related_inventory_missing']
    resources = related.get('resources')
    lists = related.get('list_snapshots')
    if (
        related.get('status') != 'read_only_related_inventory'
        or not isinstance(resources, list)
        or not isinstance(lists, list)
        or len(resources) > 300
        or len(lists) != 3 * len(namespaces)
        or type(related.get('resource_count')) is not int
        or related['resource_count'] != len(resources)
        or str(len(resources)) != cr['capsule_related_resources_count']
    ):
        reasons.append('related_inventory_incomplete')
    else:
        expected = {
            (item['name'], kind)
            for item in namespaces
            for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')
        }
        actual = {
            (item.get('namespace'), item.get('kind'))
            for item in lists if isinstance(item, Mapping)
        }
        if len(actual) != len(lists) or actual != expected:
            reasons.append('related_inventory_list_scope_changed')
        items = [_identity(item) for item in resources if isinstance(item, Mapping)]
        if len(items) != len(resources) or len(set(items)) != len(items):
            reasons.append('related_inventory_object_identity_changed')
        try:
            digest = _digest({'resources': resources, 'lists': lists})
        except (TypeError, ValueError, OverflowError):
            reasons.append('related_inventory_digest_invalid')
        else:
            if digest != cr['capsule_related_resources_sha256'] or digest != related.get('resource_sha256'):
                reasons.append('related_inventory_digest_changed')
    if not isinstance(related.get('blockers'), list) or related.get('blockers'):
        reasons.append('related_inventory_has_blockers')
    # Residual managed grants, quotas or limits always require their own exact
    # source and successor authority handoff, irrespective of manager labels.
    if isinstance(resources, list) and any(
        isinstance(row, Mapping) and row.get('origin') in ('kaori_correlated', 'ambiguous_kaori')
        for row in resources
    ):
        reasons.append('residual_kaori_resource_controls')
    quota = related.get('global_quota')
    if (
        not isinstance(quota, Mapping) or quota.get('status') != 'observed_not_handoff_authorized'
        or quota.get('scope_sha256') != cr['capsule_shared_quota_sha256']
        or not _sha(quota.get('scope_sha256'))
        or not isinstance(quota.get('resources'), list)
        or type(quota.get('count')) is not int
        or quota['count'] != len(quota['resources'])
        or not isinstance(quota.get('blockers'), list) or quota.get('blockers')
    ):
        reasons.append('global_quota_provenance_incomplete')
    lineage = related.get('rbac_lineage')
    if (
        not isinstance(lineage, Mapping)
        or lineage.get('status') != 'contract_correlated_controller_origin_unverified'
        or lineage.get('lineage_sha256') != cr['capsule_rbac_lineage_sha256']
        or not _sha(lineage.get('lineage_sha256'))
        or lineage.get('contract_correlated') is not True
        or not isinstance(lineage.get('blockers'), list) or lineage.get('blockers')
    ):
        reasons.append('rbac_contract_not_correlated')
    # Deliberate hard stop: controller-origin verification is not implemented.
    # Even fabricated controller_origin_verified=true cannot remove this gate.
    reasons.append('rbac_controller_origin_unverified')
    reasons.append('resource_specific_handoff_worklist_not_admitted')
    return reasons


def assess_capsule_handoff_admission(
    *, tenant_id: str, actor_user_id: int,
    plan: Mapping[str, Any] | None,
    approval: Mapping[str, Any] | None,
    acceptance: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    provider_authority: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Assess exact recorded evidence, never create an execution capability.

    `consistent_preconditions` means the supplied snapshots agree, NOT that
    they were freshly fetched, independent approval was exercised in reality,
    or a provider write is allowed. No positive authorization is emitted.
    """
    problems: list[str] = []
    if type(actor_user_id) is not int or not isinstance(tenant_id, str) or not tenant_id:
        raise ValueError('A canonical Tenant and authenticated actor are required.')
    if not isinstance(plan, Mapping):
        problems.append('exact_release_plan_missing')
        plan = {}
    if not isinstance(approval, Mapping):
        problems.append('independent_approval_missing')
        approval = {}
    if not isinstance(acceptance, Mapping):
        problems.append('successor_acceptance_missing')
        acceptance = {}
    if not isinstance(preflight, Mapping):
        problems.append('fresh_provider_preflight_missing')
        preflight = {}
    if not isinstance(provider_authority, Mapping):
        problems.append('fresh_provider_authority_missing')
        provider_authority = {}

    sha = plan.get('plan_sha256')
    if (
        plan.get('tenant_id') != tenant_id or plan.get('provider') != 'capsule'
        or not _sha(sha) or _plan_hash(dict(plan)) != sha
        or not _checked_recently(plan.get('requested_at'))
        or type(plan.get('requested_by')) is not int
        or actor_user_id == plan.get('requested_by')
    ):
        problems.append('release_plan_changed_or_expired')
    components = plan.get('handoff_components')
    cr: Mapping[str, Any] | None = None
    namespaces: list[dict[str, Any]] = []
    try:
        cr, namespaces = _safe_plan_inventory(plan)
        if handoff_fingerprint(components) != plan.get('handoff_fingerprint'):
            raise ValueError('Plan handoff fingerprint changed.')
    except (TypeError, ValueError, KeyError):
        problems.append('approved_capsule_scope_incomplete')
    if (
        approval.get('status') != 'acknowledged_pending_provider_handoff'
        or approval.get('plan_sha256') != sha
        or approval.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or approval.get('requested_by') != plan.get('requested_by')
        or type(approval.get('approved_by')) is not int
        or approval.get('approved_by') == plan.get('requested_by')
        or not _checked_recently(approval.get('approved_at'))
        or approval.get('provider_handoff_verified') is not False
        or approval.get('release_authorized') is not False
    ):
        problems.append('independent_approval_changed_or_expired')
    if (
        acceptance.get('status') != 'platform_admin_handoff_accepted'
        or acceptance.get('authority_mode') != 'capsule_platform_admin_governed'
        or acceptance.get('tenant_id') != tenant_id
        or acceptance.get('cluster_id') != plan.get('cluster_id')
        or acceptance.get('generation') != plan.get('generation')
        or acceptance.get('plan_sha256') != sha
        or acceptance.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or acceptance.get('provider_identity') != plan.get('provider_identity')
        or acceptance.get('successor_owner') != plan.get('successor_owner')
        or acceptance.get('reviewed_by') != approval.get('approved_by')
        or type(acceptance.get('accepted_by')) is not int
        or acceptance.get('accepted_by') != actor_user_id
        or acceptance.get('accepted_by') == plan.get('requested_by')
        or acceptance.get('consent_verified') is not True
        or acceptance.get('verified_provider_identity') is not True
        or acceptance.get('resource_authority_verified') is not True
        or not isinstance(acceptance.get('provider_username'), str)
        or not acceptance['provider_username']
        or not isinstance(acceptance.get('provider_groups'), list)
        or not acceptance['provider_groups']
        or not all(isinstance(group, str) and group for group in acceptance['provider_groups'])
        or acceptance.get('authenticated_provider') != 'kubernetes_self_subject_review'
        or acceptance.get('authorization_source') != 'kubernetes_self_subject_access_review'
        or not isinstance(acceptance.get('provider_credential_id'), str)
        or not acceptance['provider_credential_id'].startswith('X509SHA256=')
        or len(acceptance['provider_credential_id']) <= len('X509SHA256=')
        or not _checked_recently(acceptance.get('accepted_at'))
        or acceptance.get('provider_mutation_performed') is not False
        or acceptance.get('provider_handoff_verified') is not False
        or acceptance.get('release_authorized') is not False
        or acceptance.get('secret_material_persisted') is not False
    ):
        problems.append('successor_acceptance_changed_or_expired')
    if (
        preflight.get('tenant_id') != tenant_id
        or preflight.get('cluster_id') != plan.get('cluster_id')
        or preflight.get('generation') != plan.get('generation')
        or preflight.get('provider') != 'capsule'
        or preflight.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or preflight.get('live_provider_identity') != plan.get('provider_identity')
        or preflight.get('handoff_components') != components
        or preflight.get('status') not in ('blocked', 'handoff_review_required')
        or preflight.get('release_executed') is True
        or preflight.get('release_execution_available') is True
        or not _checked_recently(preflight.get('checked_at'))
    ):
        problems.append('provider_preflight_drift_or_stale')
    counts = preflight.get('dependency_counts')
    if (
        not isinstance(counts, Mapping)
        or not _REQUIRED_DEPENDENCIES.issubset(counts)
        or any(type(v) is not int or v != 0 for v in counts.values())
    ):
        problems.append('active_tenant_governance_dependencies')
    blockers = preflight.get('blockers')
    if not isinstance(blockers, list) or blockers:
        problems.append('provider_preflight_not_admitted')
    worklist_sha256: str | None = None
    manual_review_count: int | None = None
    if cr is not None:
        try:
            problems.extend(_inspect_related(snapshot=preflight, cr=cr, namespaces=namespaces))
        except (TypeError, ValueError, KeyError, OverflowError):
            # Malformed untrusted LIST or metadata must not crash the review
            # classifier or accidentally surface an admitted execution path.
            problems.append('related_inventory_malformed')
        try:
            worklist = build_capsule_handoff_worklist(
                plan=plan, related=preflight.get('capsule_related_inventory'),
            )
        except (TypeError, ValueError, KeyError):
            problems.append('provider_preservation_worklist_incomplete')
        else:
            worklist_sha256 = worklist['inventory_sha256']
            manual_review_count = worklist['manual_review_count']
    if (
        provider_authority.get('verification_source') != 'kubernetes_self_subject_review'
        or provider_authority.get('authorization_source') != 'kubernetes_self_subject_access_review'
        or provider_authority.get('provider_username') != acceptance.get('provider_username')
        or provider_authority.get('provider_groups') != acceptance.get('provider_groups')
        or not isinstance(provider_authority.get('provider_username'), str)
        or not provider_authority['provider_username']
        or not isinstance(provider_authority.get('provider_groups'), list)
        or not provider_authority['provider_groups']
        or provider_authority.get('provider_credential_id') != acceptance.get('provider_credential_id')
        or provider_authority.get('cluster_id') != str(plan.get('cluster_id') or '')
        or provider_authority.get('resource_authority_verified') is not True
        or provider_authority.get('provider_mutation_performed') is not False
    ):
        problems.append('provider_x509_ssr_sar_identity_changed')
    if cr is not None:
        try:
            scopes = _capsule_admin_scope(components)
            if (
                provider_authority.get('scoped_resources') != scopes
                or acceptance.get('scoped_resources') != scopes
                or provider_authority.get('scope_count') != len(scopes)
                or acceptance.get('scope_count') != len(scopes)
            ):
                problems.append('provider_authority_scope_changed')
        except (ValueError, TypeError):
            problems.append('provider_authority_scope_changed')

    # No live executor or authoritative Capsule controller-origin attestation is
    # implemented. Never emit 'ready' or enable dry-run/live provider mutation.
    return {
        'status': 'blocked_pending_capsule_provider_handoff',
        'tenant_id': tenant_id, 'plan_sha256': sha if _sha(sha) else None,
        'handoff_fingerprint': (
            plan.get('handoff_fingerprint')
            if _sha(plan.get('handoff_fingerprint')) else None
        ),
        'consistent_preconditions': not problems,
        'blockers': sorted(set(problems)),
        'worklist_sha256': worklist_sha256,
        'manual_review_count': manual_review_count,
        'controller_origin_verified': False,
        'dry_run_admitted': False, 'provider_execution_admitted': False,
        'resume_authorized': False, 'auto_retry_authorized': False,
        'provider_mutation_performed': False,
        'provider_handoff_verified': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
