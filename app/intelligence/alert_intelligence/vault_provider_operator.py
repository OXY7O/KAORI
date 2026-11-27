"""Internal, opt-in Vault AlertCase workflow commands; no provider mutation or delivery."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_admission import _ENABLE_ENV
from app.intelligence.alert_intelligence.vault_provider_plan import (
    _provenance_matches,
    admitted_source_state_qualified,
)
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _persisted_utc,
    _utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.audit import AuditEvent

_ACTIONS = frozenset({'acknowledge', 'assign', 'mitigating'})
_ACTIVE_WORKFLOW = frozenset({'open', 'acknowledged', 'mitigating'})


def _stop(status: str) -> str:
    db.session.rollback()
    return status


def _latest_event_id(case: AlertCase) -> int | None:
    event = (
        AlertCaseEvent.query.filter_by(case_id=case.id)
        .order_by(AlertCaseEvent.id.desc())
        .first()
    )
    return event.id if event is not None else None


def admitted_operator_workflow_qualified(case: AlertCase) -> bool:
    """Require committed workflow evidence; never infer source recovery."""
    if case.workflow_state not in _ACTIVE_WORKFLOW or case.acknowledgement_expires_at is not None:
        return False
    if (
        case.closed_at is not None
        or case.closure_reason is not None
        or case.verification_started_at is not None
    ):
        return False
    if case.workflow_state == 'open':
        if (
            case.acknowledged_at is not None
            or case.acknowledged_by_user_id is not None
            or case.mitigating_at is not None
        ):
            return False
    elif case.acknowledged_at is None or case.acknowledged_by_user_id is None:
        return False
    if (case.workflow_state == 'mitigating') != (case.mitigating_at is not None):
        return False
    event = (
        AlertCaseEvent.query.filter(
            AlertCaseEvent.case_id == case.id,
            AlertCaseEvent.event_type.in_(('acknowledged', 'assigned', 'mitigating')),
        )
        .order_by(AlertCaseEvent.id.desc())
        .first()
    )
    if event is None:
        return case.workflow_state == 'open' and case.owner_user_id is None
    metadata = event.metadata_json
    if (
        event.actor_user_id is None
        or not isinstance(metadata, dict)
        or set(metadata) != {'source_type', 'domain', 'previous_event_id', 'workflow_state', 'owner_user_id'}
        or metadata['source_type'] != 'provider_alert'
        or metadata['domain'] != 'secrets_pki'
        or metadata['workflow_state'] != case.workflow_state
        or metadata['owner_user_id'] != case.owner_user_id
        or type(metadata['previous_event_id']) is not int
        or not 0 < metadata['previous_event_id'] < event.id
    ):
        return False
    action = {'acknowledged': 'acknowledge', 'assigned': 'assign', 'mitigating': 'mitigating'}[event.event_type]
    audit = (
        AuditEvent.query.filter_by(
            target_type='alert_case',
            target_id=case.public_id,
            action='vault_provider_case_' + action,
            actor_user_id=event.actor_user_id,
        )
        .order_by(AuditEvent.id.desc())
        .first()
    )
    evidence = audit.metadata_json if audit is not None else None
    return bool(
        isinstance(evidence, dict)
        and evidence.get('case_id') == case.public_id
        and evidence.get('domain') == 'secrets_pki'
        and evidence.get('asset_key') == case.asset_key
        and evidence.get('permission_key') == 'intelligence.decisions.create'
        and isinstance(evidence.get('policy_ref'), str)
        and type(evidence.get('policy_revision')) is int
        and evidence.get('previous_event_id') == metadata['previous_event_id']
    )


def _apply_workflow(
    case: AlertCase, *, action: str, actor_id: int, owner_id: int | None, instant: datetime
) -> bool:
    """Change only existing operator workflow fields, never source or routing state."""
    if action == 'acknowledge':
        if case.workflow_state != 'open' or case.acknowledged_at is not None:
            return False
        case.acknowledged_at = instant
        # There is no eligible reminder delivery for this provider.
        case.acknowledgement_expires_at = None
        case.acknowledged_by_user_id = actor_id
        if case.owner_user_id is None:
            case.owner_user_id = actor_id
        case.workflow_state = 'acknowledged'
    elif action == 'assign':
        if case.owner_user_id == owner_id:
            return False
        case.owner_user_id = owner_id
    elif action == 'mitigating':
        if case.workflow_state != 'acknowledged' or case.owner_user_id != actor_id:
            return False
        case.workflow_state = 'mitigating'
        case.mitigating_at = instant
    else:
        return False
    return True


def _stage_evidence(
    case: AlertCase,
    *,
    action: str,
    actor_id: int,
    prior_event_id: int,
    policy_ref: str | None,
    policy_revision: int | None,
) -> None:
    event = AlertCaseEvent()
    event.case_id = case.id
    event.event_type = {'acknowledge': 'acknowledged', 'assign': 'assigned', 'mitigating': 'mitigating'}[action]
    event.actor_user_id = actor_id
    event.summary = 'A scoped operator updated the provider case workflow.'
    event.metadata_json = {
        'source_type': 'provider_alert',
        'domain': 'secrets_pki',
        'previous_event_id': prior_event_id,
        'workflow_state': case.workflow_state,
        'owner_user_id': case.owner_user_id,
    }
    db.session.add(event)
    audit = AuditEvent()
    audit.actor_user_id = actor_id
    audit.target_type = 'alert_case'
    audit.target_id = case.public_id
    audit.action = 'vault_provider_case_' + action
    audit.summary = event.summary
    audit.metadata_json = {
        'case_id': case.public_id,
        'domain': 'secrets_pki',
        'asset_key': case.asset_key,
        'permission_key': 'intelligence.decisions.create',
        'policy_ref': policy_ref,
        'policy_revision': policy_revision,
        'previous_event_id': prior_event_id,
    }
    db.session.add(audit)


def apply_vault_provider_operator_action(
    *,
    binding_id: int,
    instance_id: int,
    public_id: str,
    actor_user_id: int,
    action: str,
    expected_event_id: int,
    owner_user_id: int | None = None,
    now: datetime | None = None,
) -> str:
    """Standalone trusted command; no HTTP/worker caller and no notification.

    Lock order matches observation/admission: binding, actor scopes, snapshot,
    case. The expected latest event fences replay and concurrent changes.
    A fresh matching firing occurrence is required for every supported action.
    """
    if os.getenv(_ENABLE_ENV) != 'true':
        return 'disabled'
    instant = _utc(now or datetime.now(UTC))
    if (
        instant is None
        or any(
            type(value) is not int or value < 1
            for value in (binding_id, instance_id, actor_user_id, expected_event_id)
        )
        or not isinstance(public_id, str)
        or not 1 <= len(public_id) <= 64
        or not isinstance(action, str)
        or action not in _ACTIONS
        or (action != 'assign' and owner_user_id is not None)
        or (owner_user_id is not None and (type(owner_user_id) is not int or owner_user_id < 1))
    ):
        return 'blocked'
    try:
        eligible = _validated_binding(binding_id, now=instant, lock=True)
        if eligible is None:
            return _stop('unavailable')
        binding, source = eligible
        if binding.asset_key != str(instance_id):
            return _stop('unavailable')
        scope = evaluate_exact_vault_instance_operator_scope(
            actor_user_id=actor_user_id, instance_id=instance_id, now=instant
        )
        if not scope.allowed:
            return _stop('forbidden')
        if action == 'assign' and owner_user_id is not None and owner_user_id != actor_user_id:
            recipient = evaluate_exact_vault_instance_operator_scope(
                actor_user_id=owner_user_id, instance_id=instance_id, now=instant
            )
            if not recipient.allowed:
                return _stop('forbidden')
        snapshot = _locked_observation_snapshot(binding.asset_key)
        if snapshot is None:
            return _stop('unavailable')
        observation = read_vault_alert_observations(binding_id=binding.id, now=instant)
        if observation['state'] != 'fresh':
            return _stop('unavailable')
        case = (
            AlertCase.query.filter_by(
                public_id=public_id,
                domain='secrets_pki',
                asset_type='vault_instance',
                asset_key=binding.asset_key,
                source_type='provider_alert',
            )
            .populate_existing()
            .with_for_update(of=AlertCase)
            .first()
        )
        if (
            case is None
            or not _provenance_matches(case, source_id=source.id, binding_id=binding.id)
            or not admitted_source_state_qualified(case)
            or not admitted_operator_workflow_qualified(case)
            or case.source_state != 'firing'
            or _persisted_utc(case.last_seen_at) != _persisted_utc(snapshot.generated_at)
            or not any(
                entry['handle'] == case.case_key.removeprefix('vault-alert:')
                and entry['source_state'] == 'firing'
                for entry in observation['entries']
            )
        ):
            return _stop('unavailable')
        if _latest_event_id(case) != expected_event_id:
            return _stop('stale')
        if not _apply_workflow(
            case, action=action, actor_id=actor_user_id, owner_id=owner_user_id, instant=instant
        ):
            return _stop('unchanged')
        _stage_evidence(
            case,
            action=action,
            actor_id=actor_user_id,
            prior_event_id=expected_event_id,
            policy_ref=scope.policy_ref,
            policy_revision=scope.revision,
        )
        db.session.commit()
        return 'committed'
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return _stop('unavailable')
