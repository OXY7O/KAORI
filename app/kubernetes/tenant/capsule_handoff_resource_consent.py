"""Pure, non-executable consent manifest for each Capsule KAORI ownership candidate.

A prior plan-level human acceptance is not consent to mutate every Namespace,
ResourceQuota, LimitRange or RoleBinding. Only the exact source transfer
candidates are eligible for review; no provider-owned/foreign/quota CR may
enter this manifest. The proposed consent is NOT a committed AuditEvent,
cryptographic signer proof, or a provider PATCH authorization.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.release_handoff_approval import _checked_recently, _plan_hash

_VERSION = 'capsule-resource-successor-consent/v1'
_FIELDS = frozenset({
    'contract_version', 'tenant_id', 'cluster_id', 'generation',
    'plan_sha256', 'handoff_fingerprint', 'worklist_sha256',
    'resource_review_sha256', 'change_reference', 'reviewed_by',
    'accepted_by', 'accepted_at', 'transfer_targets',
})
_TARGET_FIELDS = frozenset({
    'kind', 'namespace', 'name', 'uid', 'resource_version',
    'policy_sha256', 'metadata_sha256', 'decision', 'proposed_label_keys',
})
_CANDIDATES = frozenset({
    'candidate_kaori_metadata_handoff_review',
    'explicit_kaori_metadata_handoff_review',
})
_ALLOWED_LABELS = {
    'Namespace': frozenset({
        'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
        'kaori.io/environment', 'kaori.io/resource-profile',
        'kaori.io/tenant-generation', 'kaori.io/profile-id',
    }),
    'ResourceQuota': frozenset({
        'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
        'kaori.io/environment', 'kaori.io/resource-profile',
        'kaori.io/tenant-generation', 'kaori.io/profile-id',
    }),
    'LimitRange': frozenset({
        'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
        'kaori.io/environment', 'kaori.io/resource-profile',
        'kaori.io/tenant-generation', 'kaori.io/profile-id',
    }),
    'RoleBinding': frozenset({
        'app.kubernetes.io/managed-by', 'kaori.io/tenant-id',
        'kaori.io/access-grant',
    }),
}


def _target_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (item['namespace'], item['kind'], item['name'])


def inspect_capsule_resource_consent(
    *, plan: Mapping[str, Any],
    resource_report: Mapping[str, Any],
    approval: Mapping[str, Any],
    acceptance: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Check one explicit source-scoped human consent proposal, never grant it."""
    if (
        not all(isinstance(item, Mapping) for item in (
            plan, resource_report, approval, acceptance, manifest,
        ))
        or set(manifest) != _FIELDS
        or manifest.get('contract_version') != _VERSION
        or plan.get('provider') != 'capsule'
        or not isinstance(plan.get('plan_sha256'), str)
        or _plan_hash(dict(plan)) != plan['plan_sha256']
        or resource_report.get('status') != 'resource_specific_controller_provenance_unverified'
        or resource_report.get('controller_origin_verified') is not False
        or resource_report.get('provider_execution_admitted') is not False
        or resource_report.get('plan_sha256') != plan['plan_sha256']
        or resource_report.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or resource_report.get('tenant_id') != plan.get('tenant_id')
        or resource_report.get('cluster_id') != plan.get('cluster_id')
    ):
        raise ValueError('Capsule per-resource consent requires the exact unadmitted plan/review.')
    if any(
        manifest.get(field) != expected for field, expected in (
            ('tenant_id', plan.get('tenant_id')),
            ('cluster_id', plan.get('cluster_id')),
            ('generation', plan.get('generation')),
            ('plan_sha256', plan['plan_sha256']),
            ('handoff_fingerprint', plan['handoff_fingerprint']),
            ('worklist_sha256', resource_report.get('worklist_sha256')),
            ('resource_review_sha256', resource_report.get('resource_review_sha256')),
            ('change_reference', plan.get('change_reference')),
        )
    ):
        raise ValueError('Capsule consent scope differs from the exact committed worklist.')
    requester = plan.get('requested_by')
    reviewer = approval.get('approved_by')
    successor = acceptance.get('accepted_by')
    if (
        type(requester) is not int or type(reviewer) is not int
        or type(successor) is not int or len({requester, reviewer, successor}) != 3
        or type(manifest.get('reviewed_by')) is not int
        or type(manifest.get('accepted_by')) is not int
        or manifest['reviewed_by'] != reviewer
        or manifest['accepted_by'] != successor
        or acceptance.get('reviewed_by') != reviewer
        or approval.get('requested_by') != requester
        or approval.get('plan_sha256') != plan['plan_sha256']
        or approval.get('status') != 'acknowledged_pending_provider_handoff'
        or acceptance.get('status') != 'platform_admin_handoff_accepted'
        or acceptance.get('plan_sha256') != plan['plan_sha256']
        or acceptance.get('tenant_id') != plan.get('tenant_id')
        or acceptance.get('cluster_id') != plan.get('cluster_id')
        or acceptance.get('generation') != plan.get('generation')
        or acceptance.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or acceptance.get('consent_verified') is not True
        or any(approval.get(key) is not False for key in (
            'provider_handoff_verified', 'release_authorized',
        ))
        or any(acceptance.get(key) is not False for key in (
            'provider_mutation_performed', 'provider_handoff_verified',
            'release_authorized', 'secret_material_persisted',
        ))
        or not _checked_recently(plan.get('requested_at'))
        or not _checked_recently(approval.get('approved_at'))
        or not _checked_recently(acceptance.get('accepted_at'))
        or not _checked_recently(manifest.get('accepted_at'))
    ):
        raise ValueError('Capsule per-resource consent lacks independent current human identities.')
    if (
        not isinstance(manifest['accepted_at'], str)
        or datetime.fromisoformat(manifest['accepted_at']).astimezone(UTC)
        < datetime.fromisoformat(acceptance['accepted_at']).astimezone(UTC)
    ):
        raise ValueError('Capsule resource consent must follow successor acceptance.')
    resources = resource_report.get('resources')
    targets = manifest.get('transfer_targets')
    if not isinstance(resources, list) or not isinstance(targets, list) or len(targets) > 300:
        raise ValueError('Capsule consent target list is malformed or unbounded.')
    candidates: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for row in resources:
        if not isinstance(row, Mapping):
            raise ValueError('Capsule source resource report is malformed.')
        if row.get('inventory_decision') not in _CANDIDATES:
            continue
        key = _target_key(row)
        if key in candidates or row.get('kind') not in _ALLOWED_LABELS:
            raise ValueError('Capsule consent source contains a duplicated/unsupported candidate.')
        if (
            row.get('controller_origin_attested') is not False
            or row.get('independent_resource_consent_verified') is not False
            or row.get('metadata_only_handoff_admitted') is not False
        ):
            raise ValueError('Capsule source incorrectly declares execution proof.')
        candidates[key] = row
    if not candidates or len(targets) != len(candidates):
        raise ValueError('Capsule successor consent omitted or added transfer candidates.')
    reviewed: list[dict[str, Any]] = []
    observed: set[tuple[str, str, str]] = set()
    for item in targets:
        if not isinstance(item, Mapping) or set(item) != _TARGET_FIELDS:
            raise ValueError('Capsule resource consent has unapproved fields or provider spec.')
        key = _target_key(item)
        source = candidates.get(key)
        if source is None or key in observed:
            raise ValueError('Capsule consent includes foreign, provider-owned or duplicate resource.')
        observed.add(key)
        if any(item.get(field) != source.get(field) for field in (
            'kind', 'namespace', 'name', 'uid', 'resource_version',
            'policy_sha256', 'metadata_sha256',
        )) or item.get('decision') != 'proposed_metadata_labels_only':
            raise ValueError('Capsule consent target is stale or attempts an unapproved operation.')
        labels = item.get('proposed_label_keys')
        if (
            not isinstance(labels, list) or not labels
            or not all(isinstance(label, str) for label in labels)
            or len(labels) != len(set(labels))
            or any(label not in _ALLOWED_LABELS[source['kind']] for label in labels)
        ):
            raise ValueError('Capsule metadata-only consent contains foreign or unsafe label keys.')
        reviewed.append({
            'kind': source['kind'], 'namespace': source['namespace'],
            'name': source['name'], 'uid': source['uid'],
            'resource_version': source['resource_version'],
            'source_policy_sha256': source.get('policy_sha256'),
            'source_metadata_sha256': source.get('metadata_sha256'),
            'label_keys_sha256': _digest(sorted(labels)),
        })
    reviewed.sort(key=lambda row: (row['namespace'], row['kind'], row['name']))
    return {
        'status': 'per_resource_successor_consent_shape_reviewed_not_committed',
        'plan_sha256': plan['plan_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'worklist_sha256': resource_report['worklist_sha256'],
        'resource_count': len(reviewed),
        'resource_consent_manifest_sha256': _digest(dict(manifest)),
        'resource_scope_sha256': _digest(reviewed),
        'independent_actor_separation_shape_valid': True,
        'consent_source_authenticated': False,
        'independent_consent_record_committed': False,
        'current_provider_uid_rv_readback_verified': False,
        'controller_origin_attested': False,
        'metadata_only_handoff_admitted': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
