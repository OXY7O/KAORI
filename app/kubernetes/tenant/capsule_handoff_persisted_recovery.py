"""Capsule interrupted-attempt recovery review, without DB or provider mutation.

Correlates a supplied chronological AuditEvent history and optional
provider read-back candidate. A read-back checksum or human review is not
independent Kubernetes authority or permission to retry.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.kubernetes.tenant.capsule_handoff_audit_envelope import (
    inspect_capsule_audit_readback_link,
)
from app.kubernetes.tenant.capsule_handoff_persistence_review import (
    inspect_capsule_persistence_snapshot,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest


def review_capsule_persisted_recovery_case(
    *,
    tenant_id: str,
    plan: Mapping[str, Any],
    related: Mapping[str, Any],
    accepted_actor_user_id: int,
    committed_rows: list[Any],
    readback_candidate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive an investigation-only recovery docket for one canonical attempt."""
    snapshot = inspect_capsule_persistence_snapshot(
        tenant_id=tenant_id,
        plan=plan,
        related=related,
        accepted_actor_user_id=accepted_actor_user_id,
        rows=committed_rows,
    )
    status = snapshot['status']
    blockers = ['audit_write_once_durability_unverified']
    correlation_sha: str | None = None
    correlated = False

    if status == 'no_attempt_observed_not_authorized':
        if readback_candidate is not None:
            raise ValueError('Capsule read-back without a recorded attempt is not admissible.')
        blockers.append('no_committed_started_event')
        recovery_state = 'no_attempt_no_execution_authority'
    elif status == 'started_outcome_unknown_recovery_required':
        if readback_candidate is not None:
            raise ValueError('Capsule STARTED without outcome cannot claim verified read-back.')
        blockers.append('provider_outcome_unknown_manual_recovery_required')
        recovery_state = 'unknown_provider_outcome_quarantined'
    elif status == 'partial_handoff_recovery_required':
        if readback_candidate is not None:
            raise ValueError('Partial Capsule receipt cannot claim complete provider read-back.')
        blockers.append('partial_provider_outcome_manual_recovery_required')
        recovery_state = 'partial_provider_outcome_quarantined'
    elif status in (
        'readback_claim_requires_independent_provider_verification',
        'manual_review_recorded_no_retry_granted',
    ):
        if readback_candidate is None:
            blockers.append('authoritative_provider_readback_missing')
            recovery_state = 'provider_readback_missing_manual_recovery'
        else:
            correlation = inspect_capsule_audit_readback_link(
                plan=plan,
                related=related,
                accepted_actor_user_id=accepted_actor_user_id,
                rows=committed_rows,
                readback_candidate=readback_candidate,
            )
            if not correlation.get('recorded_readback_matches_candidate'):
                raise ValueError('Capsule recorded provider read-back is uncorrelated.')
            correlation_sha = correlation['readback_claim_sha256']
            correlated = True
            blockers.append('authenticated_provider_readback_not_independently_verified')
            recovery_state = 'readback_correlated_but_unverified'
    else:
        raise ValueError('Unsupported Capsule audit recovery state.')

    if snapshot.get('recorded_attempt_count') != (1 if committed_rows else 0):
        raise ValueError('Capsule committed history attempt count is inconsistent.')
    return {
        'status': recovery_state,
        'tenant_id': tenant_id,
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': snapshot['worklist_sha256'],
        'attempt_id': snapshot['attempt_id'],
        'history_sha256': snapshot['history_sha256'],
        'audit_record_anchor_sha256': snapshot['audit_record_anchor_sha256'],
        'readback_claim_sha256': correlation_sha,
        'readback_claim_correlated': correlated,
        'blockers': blockers,
        'recovery_case_sha256': _digest(
            {
                'plan_sha256': plan['plan_sha256'],
                'history_sha256': snapshot['history_sha256'],
                'readback_sha256': correlation_sha,
                'blockers': blockers,
            }
        ),
        'audit_storage_append_only_verified': False,
        'audit_stream_completeness_verified': False,
        'readback_authoritative_verified': False,
        'provider_execution_admitted': False,
        'provider_handoff_verified': False,
        'provider_mutation_performed': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
