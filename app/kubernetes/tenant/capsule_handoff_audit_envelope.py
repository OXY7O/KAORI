"""Validate Capsule handoff AuditEvent envelopes without DB or Kubernetes writes.

This reader-side contract checks record order, actor attribution and the
proposed chained attempt envelope. It cannot prove the DB is append-only;
only an independently controlled audit persistence layer could establish that.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.kubernetes.tenant.capsule_handoff_attempt_state import (
    _parse_time, project_capsule_attempt_history,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

_TARGET = 'kubernetes_tenant_release_capsule_handoff_execution'
_ACTIONS = {
    'started': 'tenant.release.capsule_handoff_started',
    'partial': 'tenant.release.capsule_handoff_partial',
    'readback_candidate': 'tenant.release.capsule_handoff_readback_candidate',
    'recovery_reviewed': 'tenant.release.capsule_handoff_recovery_reviewed',
}
_MAX_ROWS = 3


def _field(item: Any, name: str) -> Any:
    return item.get(name) if isinstance(item, Mapping) else getattr(item, name, None)


def inspect_capsule_audit_event_envelopes(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    accepted_actor_user_id: int, rows: list[Any],
) -> dict[str, Any]:
    """Project supplied chronological AuditEvent records without mutating data.

    Caller must independently query a trusted, exhaustive event stream.
    Filtering or omission of an earlier attempt cannot be detected here.
    """
    if not isinstance(rows, list) or len(rows) > _MAX_ROWS:
        raise ValueError('Capsule audit attempt history must be bounded.')
    last_id = 0
    last_created: datetime | None = None
    events: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    for row in rows:
        record_id = _field(row, 'id')
        actor_id = _field(row, 'actor_user_id')
        target = _field(row, 'target_type')
        target_id = _field(row, 'target_id')
        action = _field(row, 'action')
        metadata = _field(row, 'metadata_json')
        created = _field(row, 'created_at')
        if (
            type(record_id) is not int or record_id <= last_id
            or type(actor_id) is not int or actor_id <= 0
            or target != _TARGET or target_id != plan.get('tenant_id')
            or not isinstance(metadata, Mapping)
            or not isinstance(created, (datetime, str))
        ):
            raise ValueError('Capsule AuditEvent row scope or attribution is invalid.')
        if isinstance(created, str):
            created = _parse_time(created)
        elif created.tzinfo is None or created.utcoffset() is None:
            raise ValueError('Capsule AuditEvent timestamp is not timezone-aware.')
        event_type = metadata.get('event_type')
        if (
            event_type not in _ACTIONS or action != _ACTIONS[event_type]
            or metadata.get('actor_user_id') != actor_id
            or (last_created is not None and created <= last_created)
        ):
            raise ValueError('Capsule audit event action/order does not match canonical history.')
        event_time = _parse_time(metadata.get('event_at'))
        if event_time > created:
            raise ValueError('Capsule event is recorded before its claimed creation.')
        last_created = created
        last_id = record_id
        events.append(dict(metadata))
        anchors.append({
            'audit_event_id': record_id, 'action': action,
            'event_sha256': metadata.get('event_sha256'),
        })
    projected = project_capsule_attempt_history(
        plan=plan, related=related,
        accepted_actor_user_id=accepted_actor_user_id, events=events,
    )
    return {
        **projected,
        'audit_record_count': len(anchors),
        'audit_record_anchor_sha256': _digest(anchors),
        'audit_schema_validated': True,
        'audit_stream_completeness_verified': False,
        'audit_storage_append_only_verified': False,
        'audit_db_commit_verified': False,
        'readback_authoritative_verified': False,
        'provider_handoff_verified': False,
        'provider_execution_admitted': False,
        'resume_authorized': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
    }


def inspect_capsule_audit_readback_link(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    accepted_actor_user_id: int, rows: list[Any],
    readback_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Correlate a recorded read-back claim with a pure observation candidate.

    A matching SHA/count is not independent provenance, persistence proof,
    consent or authorization. Never infer a successful provider transfer.
    """
    if not isinstance(readback_candidate, Mapping):
        raise ValueError('Capsule read-back candidate evidence is required.')
    audit = inspect_capsule_audit_event_envelopes(
        plan=plan, related=related,
        accepted_actor_user_id=accepted_actor_user_id, rows=rows,
    )
    if not rows or audit['last_event_type'] not in (
        'readback_candidate', 'recovery_reviewed',
    ):
        return {
            'status': 'no_complete_readback_claim',
            'recorded_readback_matches_candidate': False,
            'readback_authoritative_verified': False,
            'provider_handoff_verified': False,
            'resume_authorized': False, 'release_authorized': False,
        }
    source = _field(rows[-1], 'metadata_json')
    if (
        not isinstance(source, Mapping)
        or readback_candidate.get('status') != 'readback_candidate_recovery_review_required'
        or readback_candidate.get('plan_sha256') != plan.get('plan_sha256')
        or readback_candidate.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or readback_candidate.get('worklist_sha256') != audit['worklist_sha256']
        or source.get('readback_sha256') != readback_candidate.get('readback_sha256')
        or any(
            type(readback_candidate.get(key)) is not int
            or source.get(key) != readback_candidate[key]
            for key in (
                'expected_count', 'observed_count', 'pending_count',
                'transferred_count', 'ambiguous_count',
            )
        )
        or readback_candidate.get('provider_handoff_verified') is not False
        or readback_candidate.get('release_authorized') is not False
        or readback_candidate.get('provider_snapshot_authenticity_verified') is not False
    ):
        raise ValueError('Capsule audit read-back claim disagrees with observed scope.')
    return {
        'status': 'readback_claim_correlated_unverified',
        'plan_sha256': plan['plan_sha256'],
        'worklist_sha256': audit['worklist_sha256'],
        'readback_claim_sha256': audit['readback_claim_sha256'],
        'recorded_readback_matches_candidate': True,
        'audit_storage_append_only_verified': False,
        'readback_authoritative_verified': False,
        'provider_handoff_verified': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'resume_authorized': False, 'release_authorized': False,
    }


def inspect_capsule_scope_g2g3_trace(
    *, plan: Mapping[str, Any], related: Mapping[str, Any],
    accepted_actor_user_id: int, rows: list[Any],
    patch_review: Mapping[str, Any], preview_review: Mapping[str, Any],
    readback_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Tie one complete G2 preview proposal to the START/G3 event chain.

    This NEVER proves the START was durably committed before a Kubernetes
    write, the preview came from a server, or read-back was authenticated.
    A separately admitted executor must establish all those conditions.
    """
    if not all(isinstance(item, Mapping) for item in (
        plan, related, patch_review, preview_review, readback_candidate,
    )):
        raise ValueError('Capsule G2/G3 trace needs exact source and review envelopes.')
    from app.kubernetes.tenant.capsule_handoff_worklist import (
        build_capsule_handoff_worklist,
    )
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    if (
        patch_review.get('status') != 'complete_offline_scope_patch_review_unadmitted'
        or preview_review.get('status')
            != 'full_dry_run_shapes_correlated_not_provider_authenticated'
        or patch_review.get('plan_sha256') != plan.get('plan_sha256')
        or patch_review.get('handoff_fingerprint') != plan.get('handoff_fingerprint')
        or patch_review.get('worklist_sha256') != worklist['inventory_sha256']
        or preview_review.get('plan_sha256') != patch_review['plan_sha256']
        or preview_review.get('worklist_sha256') != patch_review['worklist_sha256']
        or preview_review.get('consent_manifest_sha256')
            != patch_review.get('consent_manifest_sha256')
        or preview_review.get('scope_items_sha256') != patch_review.get('scope_items_sha256')
        or type(patch_review.get('transfer_candidate_count')) is not int
        or patch_review['transfer_candidate_count'] < 1
        or patch_review['transfer_candidate_count'] != preview_review.get('scope_candidate_count')
        or preview_review.get('preview_count') != patch_review['transfer_candidate_count']
        or readback_candidate.get('plan_sha256') != plan.get('plan_sha256')
        or readback_candidate.get('worklist_sha256') != worklist['inventory_sha256']
        or readback_candidate.get('expected_count') != patch_review['transfer_candidate_count']
        or patch_review.get('provider_execution_admitted') is not False
        or patch_review.get('start_committed') is not False
        or preview_review.get('server_dry_run_completed') is not False
        or preview_review.get('provider_execution_admitted') is not False
        or readback_candidate.get('provider_handoff_verified') is not False
        or readback_candidate.get('release_authorized') is not False
    ):
        raise ValueError('Capsule preview, consent, attempt and G3 scope diverged.')
    # A caller cannot edit count/blocker rows while retaining a previously
    # recorded read-back SHA. This canonical digest check is only tamper
    # detection inside the submitted envelope, NOT provider authentication.
    receipt_fields = (
        'plan_sha256', 'handoff_fingerprint', 'worklist_sha256',
        'capsule_cr_observed', 'namespace_observations',
        'related_resource_observations', 'related_transfer_candidate_count',
        'source_namespaced_sha256', 'candidate_namespaced_sha256',
        'source_global_quota_sha256', 'candidate_global_quota_sha256',
        'expected_count', 'observed_count', 'pending_count',
        'transferred_count', 'ambiguous_count', 'blockers',
    )
    if (
        not isinstance(readback_candidate.get('readback_sha256'), str)
        or any(key not in readback_candidate for key in receipt_fields)
        or _digest({key: readback_candidate[key] for key in receipt_fields})
            != readback_candidate['readback_sha256']
    ):
        raise ValueError('Capsule G3 read-back receipt was changed after its digest was recorded.')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Capsule G2/G3 trace cannot omit the START audit claim.')
    audit = inspect_capsule_audit_event_envelopes(
        plan=plan, related=related, accepted_actor_user_id=accepted_actor_user_id,
        rows=rows,
    )
    linked = inspect_capsule_audit_readback_link(
        plan=plan, related=related, accepted_actor_user_id=accepted_actor_user_id,
        rows=rows, readback_candidate=readback_candidate,
    )
    # These two permanent source-only authority blockers must remain on
    # every read-back candidate. They forbid operational PASS, but should not
    # disguise a structurally complete metadata transfer as policy drift.
    expected_unverified = {
        'capsule_controller_provenance_unverified',
        'provider_execution_authority_unverified',
    }
    consistent = (
        linked.get('recorded_readback_matches_candidate') is True
        and audit['last_event_type'] in ('readback_candidate', 'recovery_reviewed')
        and readback_candidate.get('ambiguous_count') == 0
        and readback_candidate.get('pending_count') == 0
        and readback_candidate.get('transferred_count')
            == patch_review['transfer_candidate_count']
        and isinstance(readback_candidate.get('blockers'), list)
        and set(readback_candidate['blockers']) == expected_unverified
    )
    return {
        'status': (
            'complete_g2g3_claims_correlated_unverified'
            if consistent else 'incomplete_or_uncertain_g2g3_manual_recovery_required'
        ),
        'tenant_id': plan['tenant_id'],
        'plan_sha256': plan['plan_sha256'],
        'worklist_sha256': worklist['inventory_sha256'],
        'scope_items_sha256': patch_review['scope_items_sha256'],
        'preview_receipts_sha256': preview_review['preview_receipts_sha256'],
        'attempt_history_sha256': audit['history_sha256'],
        'readback_sha256': readback_candidate.get('readback_sha256'),
        'expected_transfer_count': patch_review['transfer_candidate_count'],
        'recorded_readback_matches_candidate': (
            linked['recorded_readback_matches_candidate']
        ),
        'all_candidates_structurally_transferred': consistent,
        'server_dry_run_source_authenticated': False,
        'start_db_commit_verified': False,
        'provider_write_order_verified': False,
        'audit_storage_append_only_verified': False,
        'readback_authoritative_verified': False,
        'independent_human_consent_authenticated': False,
        'controller_origin_attested': False,
        'provider_execution_admitted': False,
        'provider_handoff_verified': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
