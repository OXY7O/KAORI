"""Persisted recovery and closure evidence qualification, independent of current source polling."""

from __future__ import annotations

import re

from app.extensions.db import db
from app.intelligence.alert_signals.vault_authority import receipt_time
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.audit import AuditEvent

RECOVERY_EVENT = 'provider_alert_recovered'
CLOSURE_EVENT = 'provider_alert_verified_closed'
RECOVERY_REASON = 'provider_positive_recovery'
_DIGEST = re.compile(r'[a-f0-9]{64}')
_KEYS = {
    'source_type', 'domain', 'previous_event_id', 'authority_ref',
    'resolved_at', 'generation', 'policy_ref', 'policy_revision',
}


def qualified_recovery_event(event: AlertCaseEvent) -> bool:
    metadata = event.metadata_json
    return bool(
        event.event_type in (RECOVERY_EVENT, CLOSURE_EVENT)
        and isinstance(metadata, dict)
        and set(metadata) == _KEYS
        and metadata['source_type'] == 'provider_alert'
        and metadata['domain'] == 'secrets_pki'
        and type(metadata['previous_event_id']) is int
        and 0 < metadata['previous_event_id'] < event.id
        and isinstance(metadata['authority_ref'], str)
        and _DIGEST.fullmatch(metadata['authority_ref'])
        and isinstance(metadata['policy_ref'], str)
        and type(metadata['policy_revision']) is int
        and metadata['policy_revision'] > 0
        and receipt_time(metadata['resolved_at']) is not None
        and receipt_time(metadata['generation']) is not None
        and event.actor_user_id is not None
    )


def _audited_event(case: AlertCase, event_type: str) -> AlertCaseEvent | None:
    rows = (
        AlertCaseEvent.query.filter_by(case_id=case.id, event_type=event_type)
        .order_by(AlertCaseEvent.id.desc()).limit(2).all()
    )
    if len(rows) != 1 or not qualified_recovery_event(rows[0]):
        return None
    event = rows[0]
    previous = db.session.get(AlertCaseEvent, event.metadata_json['previous_event_id'])
    if previous is None or previous.case_id != case.id:
        return None
    audit = (
        AuditEvent.query.filter_by(
            target_type='alert_case', target_id=case.public_id, action=event_type, actor_user_id=event.actor_user_id
        ).order_by(AuditEvent.id.desc()).limit(2).all()
    )
    if len(audit) != 1 or audit[0].metadata_json != {
        **event.metadata_json, 'case_id': case.public_id, 'asset_key': case.asset_key
    }:
        return None
    return event


def recovery_event(case: AlertCase) -> AlertCaseEvent | None:
    resolved = _persisted_utc(case.source_resolved_at)
    seen = _persisted_utc(case.last_seen_at)
    changed = _persisted_utc(case.source_state_changed_at)
    started = _persisted_utc(case.verification_started_at)
    if (
        case.source_state != 'resolved' or case.source_state_reason != RECOVERY_REASON
        or case.workflow_state not in ('verification_pending', 'closed')
        or any(value is None for value in (resolved, seen, changed, started))
    ):
        return None
    if not (seen is not None and resolved is not None and changed is not None and started is not None):
        return None
    if not seen < resolved <= changed <= started or case.acknowledgement_expires_at is not None:
        return None
    event = _audited_event(case, RECOVERY_EVENT)
    if event is None or receipt_time(event.metadata_json['resolved_at']) != resolved:
        return None
    if receipt_time(event.metadata_json['generation']) != changed:
        return None
    return event


def admitted_recovery_qualified(case: AlertCase) -> bool:
    recovered = recovery_event(case)
    if recovered is None:
        return False
    if case.workflow_state == 'verification_pending':
        return case.closed_at is None and case.closure_reason is None and case.closed_by_user_id is None
    closure = _audited_event(case, CLOSURE_EVENT)
    closed = _persisted_utc(case.closed_at)
    started = _persisted_utc(case.verification_started_at)
    if closure is None or closed is None or started is None:
        return False
    generation = receipt_time(closure.metadata_json['generation'])
    return bool(
        case.closure_reason == 'resolved'
        and case.closed_by_user_id == closure.actor_user_id
        and closure.actor_user_id != recovered.actor_user_id
        and closure.metadata_json['previous_event_id'] == recovered.id
        and closure.metadata_json['resolved_at'] == recovered.metadata_json['resolved_at']
        and closure.metadata_json['authority_ref'] != recovered.metadata_json['authority_ref']
        and generation is not None and started < generation <= closed
        and case.resolution_summary and case.verification_evidence and case.remediation_steps_json
    )
