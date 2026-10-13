"""Validate proposed Capsule handoff attempt history without executing it (#1229).

An append-only SQL AuditEvent and a Kubernetes PATCH cannot be transactional.
Unknown provider outcomes must remain recovery-blocked, even after a restart.
This pure projection is NOT the operational writer, authority proof, or finalizer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest
from app.kubernetes.tenant.capsule_handoff_worklist import build_capsule_handoff_worklist
from app.kubernetes.tenant.release_handoff_approval import _plan_hash

_SCHEMA = 'capsule-handoff-attempt/v1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_MAX_HISTORY = 3
_STATES = {
    'started': 'unknown',
    'partial': 'unknown',
    'readback_candidate': 'readback_observed',
    'recovery_reviewed': 'review_only',
}
_EVENT_KEYS = frozenset(
    {
        'contract_version',
        'event_type',
        'attempt_id',
        'sequence',
        'event_at',
        'tenant_id',
        'cluster_id',
        'generation',
        'plan_sha256',
        'handoff_fingerprint',
        'worklist_sha256',
        'actor_user_id',
        'previous_event_sha256',
        'event_sha256',
        'outcome',
        'readback_sha256',
        'expected_count',
        'observed_count',
        'pending_count',
        'transferred_count',
        'ambiguous_count',
        'provider_handoff_verified',
        'release_authorized',
        'resume_authorized',
        'auto_retry_authorized',
        'secret_material_persisted',
    }
)
_TRANSFER_DECISIONS = frozenset(
    {
        'candidate_kaori_metadata_handoff_review',
        'explicit_kaori_metadata_handoff_review',
    }
)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Capsule attempt event timestamp is missing.')
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Capsule attempt event timestamp is malformed.') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Capsule attempt event timestamp must have a timezone.')
    return result


def _event_checksum(event: Mapping[str, Any]) -> str:
    """Canonical event checksum only; NOT an authenticated tamper-proof audit."""
    return _digest({key: value for key, value in event.items() if key != 'event_sha256'})


def _require_prior_event(prior: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Do not compare a recovery claim with absent immutable predecessor evidence."""
    if prior is None:
        raise ValueError('Capsule recovery review requires prior immutable provider evidence.')
    return prior


def _validate_event(
    *,
    event: Mapping[str, Any],
    index: int,
    prior: Mapping[str, Any] | None,
    plan: Mapping[str, Any],
    worklist: Mapping[str, Any],
    accepted_actor_user_id: int,
) -> None:
    if set(event) != _EVENT_KEYS:
        raise ValueError('Capsule attempt receipt schema is unknown or contains unapproved fields.')
    eid = event['attempt_id']
    try:
        attempt_uuid = UUID(str(eid))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Capsule attempt ID must be a UUID.') from exc
    if str(attempt_uuid) != eid:
        raise ValueError('Capsule attempt ID is not canonical UUID text.')
    if (
        event['contract_version'] != _SCHEMA
        or event['event_type'] not in _STATES
        or type(event['sequence']) is not int
        or event['sequence'] != index + 1
        or type(event['actor_user_id']) is not int
        or event['actor_user_id'] <= 0
        or (
            event['actor_user_id'] == accepted_actor_user_id
            if event['event_type'] == 'recovery_reviewed'
            else event['actor_user_id'] != accepted_actor_user_id
        )
        or event['tenant_id'] != plan.get('tenant_id')
        or event['cluster_id'] != plan.get('cluster_id')
        or event['generation'] != plan.get('generation')
        or event['plan_sha256'] != plan.get('plan_sha256')
        or event['handoff_fingerprint'] != plan.get('handoff_fingerprint')
        or event['worklist_sha256'] != worklist.get('inventory_sha256')
        or event['outcome'] != _STATES[event['event_type']]
        or any(
            event[key] is not False
            for key in (
                'provider_handoff_verified',
                'release_authorized',
                'resume_authorized',
                'auto_retry_authorized',
                'secret_material_persisted',
            )
        )
        or not _sha(event['event_sha256'])
        or event['event_sha256'] != _event_checksum(event)
    ):
        raise ValueError('Capsule attempt event is not bound to its canonical denied scope.')
    timestamp = _parse_time(event['event_at'])
    if prior is None:
        if (
            event['event_type'] != 'started'
            or event['previous_event_sha256'] is not None
            or event['readback_sha256'] is not None
            or any(
                event[k] != 0
                for k in (
                    'observed_count',
                    'pending_count',
                    'transferred_count',
                    'ambiguous_count',
                )
            )
        ):
            raise ValueError('Capsule attempt must start with immutable pre-write evidence.')
    else:
        if (
            event['event_type'] == 'started'
            or eid != prior['attempt_id']
            or event['previous_event_sha256'] != prior['event_sha256']
            or timestamp <= _parse_time(prior['event_at'])
        ):
            raise ValueError('Capsule attempt history is forked, replayed or out of order.')
        if index == 1 and event['event_type'] not in ('partial', 'readback_candidate'):
            raise ValueError('Capsule attempt needs provider outcome review after start.')
        if index == 2 and (
            prior['event_type'] not in ('partial', 'readback_candidate') or event['event_type'] != 'recovery_reviewed'
        ):
            raise ValueError('Only an explicit review may follow an uncertain provider outcome.')
        if index > 2:
            raise ValueError('Further Capsule attempts require a new separately admitted workflow.')

    expected_count = sum(row['decision'] in _TRANSFER_DECISIONS for row in worklist['items'])
    if expected_count < 1:
        raise ValueError('Capsule attempt has no exact KAORI ownership transfer candidates.')
    counts = tuple(
        event[k]
        for k in (
            'expected_count',
            'observed_count',
            'pending_count',
            'transferred_count',
            'ambiguous_count',
        )
    )
    if any(type(v) is not int or v < 0 for v in counts) or event['expected_count'] != expected_count:
        raise ValueError('Capsule attempted transfer count disagrees with the approved worklist.')
    if event['event_type'] == 'started':
        if event['readback_sha256'] is not None:
            raise ValueError('Start cannot assert completed read-back.')
    elif event['event_type'] == 'partial':
        if (
            event['readback_sha256'] is not None
            or event['observed_count'] > expected_count
            or event['transferred_count'] > event['observed_count']
            or event['pending_count'] > event['observed_count']
            or event['ambiguous_count'] > event['observed_count']
            or (
                event['pending_count'] + event['transferred_count'] + event['ambiguous_count'] > event['observed_count']
            )
        ):
            raise ValueError('Partial provider outcome is incomplete or was overstated.')
    elif event['event_type'] == 'readback_candidate':
        if (
            not _sha(event['readback_sha256'])
            or event['observed_count'] != expected_count
            or event['pending_count'] + event['transferred_count'] + event['ambiguous_count'] != expected_count
        ):
            raise ValueError('Full Capsule read-back claim has missing/ambiguous scope.')
    else:
        prior = _require_prior_event(prior)
        if (
            event['readback_sha256'] != prior['readback_sha256']
            or event['observed_count'] != prior['observed_count']
            or event['transferred_count'] != prior['transferred_count']
            or event['pending_count'] != prior['pending_count']
            or event['ambiguous_count'] != prior['ambiguous_count']
        ):
            raise ValueError('Human recovery review cannot rewrite immutable provider observations.')


def project_capsule_attempt_history(
    *,
    plan: Mapping[str, Any],
    related: Mapping[str, Any],
    accepted_actor_user_id: int,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Project a single attempt for operator recovery only, never provider retry.

    Callers may inspect copies of committed append-only events, but cannot use
    this projection as evidence of a real provider read-back or consent.
    """
    if (
        not isinstance(plan, Mapping)
        or not isinstance(related, Mapping)
        or type(accepted_actor_user_id) is not int
        or accepted_actor_user_id <= 0
        or not isinstance(events, list)
        or len(events) > _MAX_HISTORY
        or any(not isinstance(event, Mapping) for event in events)
        or not isinstance(plan.get('plan_sha256'), str)
        or _plan_hash(dict(plan)) != plan['plan_sha256']
    ):
        raise ValueError('Canonical Capsule attempt context or approved plan is missing.')
    worklist = build_capsule_handoff_worklist(plan=plan, related=related)
    for index, event in enumerate(events):
        _validate_event(
            event=event,
            index=index,
            prior=events[index - 1] if index else None,
            plan=plan,
            worklist=worklist,
            accepted_actor_user_id=accepted_actor_user_id,
        )
    if not events:
        state = 'no_attempt_observed_not_authorized'
    elif events[-1]['event_type'] == 'started':
        state = 'started_outcome_unknown_recovery_required'
    elif events[-1]['event_type'] == 'partial':
        state = 'partial_handoff_recovery_required'
    elif events[-1]['event_type'] == 'readback_candidate':
        state = 'readback_claim_requires_independent_provider_verification'
    else:
        state = 'manual_review_recorded_no_retry_granted'
    return {
        'status': state,
        'tenant_id': plan['tenant_id'],
        'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': worklist['inventory_sha256'],
        'attempt_id': events[0]['attempt_id'] if events else None,
        'event_count': len(events),
        'history_sha256': _digest([event['event_sha256'] for event in events]),
        'last_event_type': events[-1]['event_type'] if events else None,
        'readback_claim_sha256': events[-1]['readback_sha256'] if events else None,
        'readback_authoritative_verified': False,
        'successor_consent_reverified': False,
        'provider_handoff_verified': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'resume_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
