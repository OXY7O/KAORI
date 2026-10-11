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
