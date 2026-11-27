"""Local-only scoped recovery and independent verification of provider-signed evidence.

No source mutation, generic lifecycle bypass, automatic resolution, or delivery.
Both commands requalify the locked, current active and recovery generations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope, lock_explicit_permissions
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_admission import local_reconcile_enabled
from app.intelligence.alert_intelligence.vault_provider_operator import (
    _latest_event_id,
    admitted_operator_workflow_qualified,
)
from app.intelligence.alert_intelligence.vault_provider_plan import _provenance_matches, admitted_source_state_qualified
from app.intelligence.alert_intelligence.vault_recovery_state import (
    CLOSURE_EVENT,
    RECOVERY_EVENT,
    RECOVERY_REASON,
    admitted_recovery_qualified,
    recovery_event,
)
from app.intelligence.alert_signals.vault_authority import receipt_time
from app.intelligence.alert_signals.vault_recovery import read_vault_recovery
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _persisted_utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.audit import AuditEvent

_ACTIONS = {'admit_recovery', 'verify_close'}
_PERMISSIONS = {'intelligence.view', 'intelligence.decisions.create', 'secrets_pki.view'}


@dataclass(frozen=True, slots=True)
class _RecoveryCandidate:
    case: AlertCase
    action: str
    generation: datetime
    resolved: datetime
    evidence_ref: str
    prior_event: int
    policy_ref: str
    policy_revision: int


def _action_for(case: AlertCase, *, actor_id: int, generation: datetime, resolved: datetime) -> str | None:
    seen = _persisted_utc(case.last_seen_at)
    if seen is None or resolved <= seen:
        return None
    if case.source_state in ('firing', 'unknown'):
        changed = _persisted_utc(case.source_state_changed_at)
        if changed is None or generation <= changed:
            return None
        if admitted_source_state_qualified(case) and admitted_operator_workflow_qualified(case):
            return 'admit_recovery'
        return None
    if case.workflow_state != 'verification_pending' or not admitted_recovery_qualified(case):
        return None
    recovered = recovery_event(case)
    started = _persisted_utc(case.verification_started_at)
    if (
        recovered is None or recovered.actor_user_id == actor_id
        or started is None or generation <= started
        or resolved != _persisted_utc(case.source_resolved_at)
    ):
        return None
    return 'verify_close'


def _qualify(
    *, binding_id: int, instance_id: int, public_id: str, actor_id: int, expected_event_id: int, now: datetime
) -> _RecoveryCandidate | None:
    eligible = _validated_binding(binding_id, now=now, lock=True)
    if eligible is None:
        return None
    binding, source = eligible
    if binding.asset_key != str(instance_id) or not lock_explicit_permissions(actor_id, _PERMISSIONS):
        return None
    grant = evaluate_exact_vault_instance_operator_scope(actor_user_id=actor_id, instance_id=instance_id, now=now)
    if not grant.allowed or not isinstance(grant.policy_ref, str) or type(grant.revision) is not int:
        return None
    snapshot = _locked_observation_snapshot(binding.asset_key)
    generation = _persisted_utc(snapshot.generated_at) if snapshot is not None else None
    if generation is None:
        return None
    active = read_vault_alert_observations(binding_id=binding.id, now=now)
    if active['state'] not in ('fresh', 'unobserved'):
        return None
    evidence = read_vault_recovery(binding=binding, source=source, observed=generation, now=now)
    if evidence is None:
        return None
    case = (
        AlertCase.query.filter_by(
            public_id=public_id, domain='secrets_pki', asset_type='vault_instance',
            asset_key=binding.asset_key, source_type='provider_alert'
        ).populate_existing().with_for_update(of=AlertCase).first()
    )
    if case is None or not _provenance_matches(case, source_id=source.id, binding_id=binding.id):
        return None
    if _latest_event_id(case) != expected_event_id:
        return None
    handle = case.case_key.removeprefix('vault-alert:')
    if any(entry['handle'] == handle for entry in (active['entries'] or [])):
        return None
    matches = [entry for entry in evidence['entries'] if entry['handle'] == handle]
    if len(matches) != 1:
        return None
    resolved = receipt_time(matches[0]['resolved_at'])
    if resolved is None:
        return None
    action = _action_for(case, actor_id=actor_id, generation=generation, resolved=resolved)
    if action is None:
        return None
    return _RecoveryCandidate(
        case, action, generation, resolved, evidence['evidence_ref'], expected_event_id, grant.policy_ref, grant.revision
    )


def _record(candidate: _RecoveryCandidate, *, actor_id: int, now: datetime) -> None:
    case = candidate.case
    if candidate.action == 'admit_recovery':
        case.source_state = 'resolved'
        case.source_state_reason = RECOVERY_REASON
        case.source_resolved_at = candidate.resolved
        case.source_state_changed_at = candidate.generation
        case.workflow_state = 'verification_pending'
        case.verification_started_at = now
        event_type = RECOVERY_EVENT
        summary = 'Positive provider resolution evidence admitted; independent verification required.'
    else:
        from app.intelligence.alert_intelligence.lifecycle import _requires_postmortem

        case.workflow_state = 'closed'
        case.closure_reason = 'resolved'
        case.closed_at = now
        case.closed_by_user_id = actor_id
        case.resolution_summary = 'Provider resolution independently verified.'
        case.remediation_steps_json = ['Rechecked explicit provider resolution and a newer committed source generation.']
        case.verification_evidence = 'Signed occurrence evidence and independent scoped verification committed.'
        case.postmortem_required = _requires_postmortem(case)
        case.postmortem_status = 'required' if case.postmortem_required else 'not_required'
        event_type = CLOSURE_EVENT
        summary = 'Independent scoped operator verified provider resolution and closed the case.'
    metadata = {
        'source_type': 'provider_alert',
        'domain': 'secrets_pki',
        'previous_event_id': candidate.prior_event,
        'authority_ref': candidate.evidence_ref,
        'resolved_at': candidate.resolved.isoformat(),
        'generation': candidate.generation.isoformat(),
        'policy_ref': candidate.policy_ref,
        'policy_revision': candidate.policy_revision,
    }
    event = AlertCaseEvent()
    event.case_id = case.id
    event.event_type = event_type
    event.actor_user_id = actor_id
    event.summary = summary
    event.metadata_json = metadata
    audit = AuditEvent()
    audit.actor_user_id = actor_id
    audit.target_type = 'alert_case'
    audit.target_id = case.public_id
    audit.action = event_type
    audit.summary = summary
    audit.metadata_json = {**metadata, 'case_id': case.public_id, 'asset_key': case.asset_key}
    db.session.add_all((event, audit))


def local_recovery_action(
    *, binding_id: int, instance_id: int, public_id: str, actor_id: int, expected_event_id: int, action: str
) -> str:
    """Preview or execute a local action; never accept client-supplied evidence."""
    if not local_reconcile_enabled() or action not in _ACTIONS | {'preview'}:
        return 'disabled'
    now = datetime.now(UTC)
    try:
        candidate = _qualify(
            binding_id=binding_id, instance_id=instance_id, public_id=public_id,
            actor_id=actor_id, expected_event_id=expected_event_id, now=now,
        )
        if candidate is None:
            return 'unavailable'
        if action == 'preview':
            return candidate.action
        if candidate.action != action:
            return 'unavailable'
        _record(candidate, actor_id=actor_id, now=now)
        db.session.commit()
        return 'committed'
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return 'unavailable'
    finally:
        db.session.rollback()
