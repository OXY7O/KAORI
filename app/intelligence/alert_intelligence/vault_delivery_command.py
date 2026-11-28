"""Local-only scoped firing claim using the canonical notification journal and sender.

A durable claim precedes network I/O. Recheck the same independent approval
under locks before sending. Ambiguous outcomes are never eligible for retry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope, lock_explicit_permissions
from app.common.pagination import paginate_sequence
from app.extensions.db import db
from app.integrations.delivery.notification_channels.catalog import domain_event_allowed
from app.integrations.delivery.notification_channels.config import notification_delivery_max_attempts
from app.integrations.delivery.notification_channels.contracts import DeliveryResult, NotificationMessage
from app.integrations.delivery.notification_channels.service import (
    _begin_delivery_attempt,
    _deliver,
    _record_delivery_outcome,
    _replay_message,
)
from app.intelligence.alert_intelligence.vault_delivery_authority import qualify_destination_receipt
from app.intelligence.alert_intelligence.vault_delivery_journal import (
    CLAIM_ACTION, CLAIM_KEY, OUTCOME_ACTION, REJECTION_KEY, audited_claim, audited_outcome, claim_exists, firing_journal,
)
from app.intelligence.alert_intelligence.vault_provider_admission import local_reconcile_enabled
from app.intelligence.alert_intelligence.vault_provider_delivery import (
    _channel_matches_candidate,
    _policy_matches_exact_source,
)
from app.intelligence.alert_intelligence.vault_provider_operator import _current_firing_case
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _persisted_utc,
    _validated_binding,
    read_vault_alert_observations,
    source_revision,
)
from app.models.alert_ops import AlertCase, AlertRoutingPolicy
from app.models.audit import AuditEvent
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.security.credentials import CredentialEncryptionError

_PERMISSIONS = {'integrations.manage', 'intelligence.view', 'intelligence.decisions.create', 'secrets_pki.view'}


@dataclass(frozen=True, slots=True)
class DeliveryIntent:
    instance_id: int
    binding_id: int
    actor_id: int
    case_id: str
    policy_id: int
    channel_id: int


@dataclass(frozen=True, slots=True)
class _Target:
    case: AlertCase
    policy: AlertRoutingPolicy
    channel: NotificationChannel
    receipt_ref: str


def _valid_intent(intent: DeliveryIntent) -> bool:
    return (
        isinstance(intent, DeliveryIntent)
        and all(
            type(value) is int and 0 < value <= 2_147_483_647
            for value in (intent.instance_id, intent.binding_id, intent.actor_id, intent.policy_id, intent.channel_id)
        )
        and isinstance(intent.case_id, str)
        and 1 <= len(intent.case_id) <= 64
    )


def _scope(actor_id: int, instance_id: int, *, now: datetime) -> bool:
    return lock_explicit_permissions(actor_id, _PERMISSIONS) and evaluate_exact_vault_instance_operator_scope(
        actor_user_id=actor_id, instance_id=instance_id, now=now
    ).allowed


def _qualify(intent: DeliveryIntent, *, now: datetime) -> _Target | None:
    eligible = _validated_binding(intent.binding_id, now=now, lock=True)
    if eligible is None:
        return None
    binding, source = eligible
    if binding.asset_key != str(intent.instance_id) or not _scope(intent.actor_id, intent.instance_id, now=now):
        return None
    snapshot = _locked_observation_snapshot(binding.asset_key)
    if snapshot is None:
        return None
    observation = read_vault_alert_observations(binding_id=binding.id, now=now)
    if observation['state'] != 'fresh':
        return None
    case = (
        AlertCase.query.filter_by(
            public_id=intent.case_id,
            domain='secrets_pki',
            asset_type='vault_instance',
            asset_key=binding.asset_key,
            source_type='provider_alert',
        )
        .populate_existing()
        .with_for_update(of=AlertCase)
        .first()
    )
    if case is None or case.workflow_state != 'open' or case.acknowledged_at is not None:
        return None
    if not _current_firing_case(
        case,
        source_id=source.id,
        binding_id=binding.id,
        generated_at=snapshot.generated_at,
        entries=observation['entries'],
    ):
        return None
    return _qualify_target(case, intent=intent, now=now)


def _qualify_target(case: AlertCase, *, intent: DeliveryIntent, now: datetime) -> _Target | None:
    policy = db.session.get(AlertRoutingPolicy, intent.policy_id, populate_existing=True, with_for_update=True)
    channel = db.session.get(NotificationChannel, intent.channel_id, populate_existing=True, with_for_update=True)
    if policy is None or channel is None:
        return None
    if not domain_event_allowed('secrets_pki', 'alert_ops.firing'):
        return None
    if not _policy_matches_exact_source(policy, case=case, binding_id=intent.binding_id, channel_id=channel.id):
        return None
    if not _channel_matches_candidate(channel, severity=case.severity, now=now):
        return None
    receipt = qualify_destination_receipt(
        case, binding_id=intent.binding_id, policy=policy, channel=channel, actor_id=intent.actor_id, now=now
    )
    return _Target(case, policy, channel, receipt) if receipt is not None else None


def _message(case: AlertCase) -> NotificationMessage:
    return NotificationMessage(
        title='KAORI · Secrets & PKI alert',
        body='A qualified provider alert is firing. Review the authorized Alert Intelligence workspace.',
        severity=case.severity,
    )


def _claim_metadata(intent: DeliveryIntent, target: _Target) -> dict[str, object]:
    return {
        'case_id': intent.case_id,
        'binding_id': intent.binding_id,
        'policy_id': intent.policy_id,
        'channel_id': intent.channel_id,
        'receipt_ref': target.receipt_ref,
        'maker_id': intent.actor_id,
    }


def _matching_claim(row: NotificationDelivery, intent: DeliveryIntent) -> bool:
    claim = (row.payload_json or {}).get(CLAIM_KEY)
    return bool(
        isinstance(claim, dict)
        and row.domain == 'secrets_pki'
        and row.asset_type == 'vault_instance'
        and row.asset_key == str(intent.instance_id)
        and row.channel_id == intent.channel_id
        and row.event_key == f'alert-case:{intent.case_id}:firing:scoped-v1'
        and claim.get('case_id') == intent.case_id
        and claim.get('binding_id') == intent.binding_id
        and claim.get('policy_id') == intent.policy_id
        and claim.get('channel_id') == intent.channel_id
        and claim.get('maker_id') == intent.actor_id
    )


def _retry_allowed(row: NotificationDelivery, *, intent: DeliveryIntent, target: _Target, now: datetime) -> bool:
    payload = row.payload_json or {}
    due = _persisted_utc(row.next_retry_at)
    claim = payload.get(CLAIM_KEY)
    return bool(
        _matching_claim(row, intent)
        and row.status in ('failed', 'skipped')
        and payload.get(REJECTION_KEY) is True
        and audited_outcome(target.case, row) == 'rejected'
        and isinstance(claim, dict)
        and claim.get('receipt_ref') != target.receipt_ref
        and due is not None
        and due <= now
        and 0 < row.attempt_count < notification_delivery_max_attempts()
        and _replay_message(row, target.channel) == _message(target.case)
    )


def _stage_claim_audit(intent: DeliveryIntent, target: _Target, *, attempt: int) -> None:
    db.session.add(
        AuditEvent(
            actor_user_id=intent.actor_id,
            target_type='alert_case',
            target_id=intent.case_id,
            action=CLAIM_ACTION,
            summary='An independently approved local firing attempt was reserved.',
            metadata_json={**_claim_metadata(intent, target), 'attempt': attempt, 'domain': 'secrets_pki'},
        )
    )


def _new_journal(intent: DeliveryIntent, target: _Target) -> NotificationDelivery:
    row = NotificationDelivery()
    row.channel_id = intent.channel_id
    row.event_key = f'alert-case:{intent.case_id}:firing:scoped-v1'
    row.event_type = 'alert_ops.firing'
    row.domain = 'secrets_pki'
    row.asset_type = 'vault_instance'
    row.asset_key = str(intent.instance_id)
    row.severity = target.case.severity
    row.status = 'queued'
    row.attempt_count = 0
    row.payload_json = {}
    db.session.add(row)
    db.session.flush()
    return row


def _reserve(intent: DeliveryIntent, target: _Target, *, retry: bool, now: datetime) -> tuple[int, int, str] | None:
    rows = firing_journal(target.case, lock=True)
    if retry:
        if len(rows) != 1 or not _retry_allowed(rows[0], intent=intent, target=target, now=now):
            return None
        row = rows[0]
    else:
        if rows or claim_exists(target.case):
            return None
        row = _new_journal(intent, target)
    row.payload_json = {**(row.payload_json or {}), CLAIM_KEY: _claim_metadata(intent, target), REJECTION_KEY: False}
    attempt = row.attempt_count + 1
    row_id = row.id
    _stage_claim_audit(intent, target, attempt=attempt)
    _begin_delivery_attempt(row, target.channel, _message(target.case))
    return row_id, attempt, target.receipt_ref


def _send_claimed(intent: DeliveryIntent, *, claim: tuple[int, int, str]) -> str:
    row_id, attempt, receipt = claim
    target = _qualify(intent, now=datetime.now(UTC))
    if target is None or target.receipt_ref != receipt:
        return 'claimed_review_required'
    row = db.session.get(NotificationDelivery, row_id, populate_existing=True, with_for_update=True)
    if row is None or not _matching_claim(row, intent) or row.status != 'queued' or row.attempt_count != attempt:
        return 'claimed_review_required'
    if audited_claim(target.case, row) != _claim_metadata(intent, target):
        return 'claimed_review_required'
    message = _replay_message(row, target.channel)
    if message is None or message != _message(target.case):
        return 'claimed_review_required'
    # Requalified locks remain held during the bounded existing provider call.
    result = _deliver(target.channel, message)
    definitive = not result.success and result.definitively_rejected and result.retry_after_seconds is not None
    row.payload_json = {**(row.payload_json or {}), REJECTION_KEY: definitive}
    sanitized = DeliveryResult(
        result.success,
        'Provider accepted the approved alert.' if result.success else 'Provider did not confirm delivery.',
        retry_after_seconds=result.retry_after_seconds if definitive else None,
    )
    outcome = 'sent' if result.success else ('rejected' if definitive else 'unconfirmed')
    db.session.add(
        AuditEvent(
            actor_user_id=intent.actor_id, target_type='alert_case', target_id=intent.case_id,
            action=OUTCOME_ACTION, summary='Scoped provider delivery outcome recorded.',
            metadata_json={
                **_claim_metadata(intent, target), 'attempt': attempt, 'domain': 'secrets_pki', 'result': outcome
            },
        )
    )
    _record_delivery_outcome(row, target.channel, sanitized)
    return 'sent' if result.success else ('retry_review_required' if definitive else 'outcome_review_required')


def execute_local_vault_delivery(intent: DeliveryIntent, *, retry: bool = False) -> str:
    if not local_reconcile_enabled() or not _valid_intent(intent) or type(retry) is not bool:
        return 'disabled'
    try:
        now = datetime.now(UTC)
        target = _qualify(intent, now=now)
        if target is None:
            return 'unavailable'
        claim = _reserve(intent, target, retry=retry, now=now)
        if claim is None:
            return 'prior_delivery_review_required'
        return _send_claimed(intent, claim=claim)
    except (SQLAlchemyError, CredentialEncryptionError, ValueError, TypeError, AttributeError, OSError):
        return 'outcome_review_required'
    finally:
        db.session.rollback()


def create_local_vault_policy(*, instance_id: int, binding_id: int, actor_id: int, channel_id: int) -> int | None:
    """Create one dedicated candidate; not a destination approval or generic policy."""
    if not local_reconcile_enabled() or any(
        type(v) is not int or not 0 < v <= 2_147_483_647
        for v in (instance_id, binding_id, actor_id, channel_id)
    ):
        return None
    try:
        now = datetime.now(UTC)
        eligible = _validated_binding(binding_id, now=now, lock=True)
        if eligible is None or eligible[0].asset_key != str(instance_id):
            return None
        if not _scope(actor_id, instance_id, now=now):
            return None
        channel = db.session.get(NotificationChannel, channel_id, populate_existing=True, with_for_update=True)
        if channel is None or not _channel_matches_candidate(channel, severity='critical', now=now):
            return None
        existing = _scoped_policies(instance_id, binding_id)
        if existing is None:
            return None
        candidates = [row for row in existing if row.enabled and row.channel_ids_json == [channel.id]]
        if candidates:
            return candidates[0].id if len(candidates) == 1 else None
        if len(existing) >= _MAX_POLICIES:
            return None
        policy = AlertRoutingPolicy()
        policy.name = 'Vault scoped firing candidate'
        policy.enabled = True
        policy.domains_json = ['secrets_pki']
        policy.source_types_json = ['provider_alert']
        policy.matchers_json = {'vault_instance': str(instance_id), 'source_binding_id': str(binding_id)}
        policy.severities_json = ['critical', 'warning', 'info']
        policy.channel_ids_json = [channel.id]
        policy.send_resolved = False
        policy.created_by_user_id = actor_id
        policy.updated_by_user_id = actor_id
        db.session.add(policy)
        db.session.flush()
        policy_id = policy.id
        db.session.add(
            AuditEvent(
                actor_user_id=actor_id,
                target_type='alert_routing_policy',
                target_id=str(policy_id),
                action='vault_provider_routing_candidate_created',
                summary='Local exact-source firing candidate created; destination approval still required.',
                metadata_json={'instance_id': instance_id, 'binding_id': binding_id, 'channel_id': channel_id},
            )
        )
        db.session.commit()
        return policy_id
    except (SQLAlchemyError, CredentialEncryptionError, ValueError, TypeError, AttributeError):
        return None
    finally:
        db.session.rollback()


_MAX_POLICIES = 100


def _scoped_policies(instance_id: int, binding_id: int) -> list[AlertRoutingPolicy] | None:
    rows = (
        AlertRoutingPolicy.query.filter(
            AlertRoutingPolicy.matchers_json['vault_instance'].as_string() == str(instance_id),
            AlertRoutingPolicy.matchers_json['source_binding_id'].as_string() == str(binding_id),
        )
        .order_by(AlertRoutingPolicy.id.desc())
        .limit(_MAX_POLICIES + 1)
        .populate_existing()
        .all()
    )
    if len(rows) > _MAX_POLICIES:
        return None
    return [
        row for row in rows
        if row.domains_json == ['secrets_pki'] and row.source_types_json == ['provider_alert']
        and row.matchers_json == {'vault_instance': str(instance_id), 'source_binding_id': str(binding_id)}
        and isinstance(row.channel_ids_json, list) and len(row.channel_ids_json) == 1
        and type(row.channel_ids_json[0]) is int and not row.send_resolved
    ]


def _policy_projection(policy: AlertRoutingPolicy) -> dict[str, Any]:
    channel_id = policy.channel_ids_json[0]
    # Do not load the credential-bearing channel entity for this display.
    channel = db.session.query(
        NotificationChannel.updated_at, NotificationChannel.last_tested_at,
        NotificationChannel.enabled, NotificationChannel.lifecycle_state, NotificationChannel.test_status,
    ).filter(NotificationChannel.id == channel_id).first()
    revision = _persisted_utc(policy.updated_at)
    channel_revision = _persisted_utc(channel.updated_at) if channel is not None else None
    tested = _persisted_utc(channel.last_tested_at) if channel is not None else None
    return {
        'id': policy.id, 'channel_id': channel_id, 'enabled': policy.enabled,
        'revision': revision.isoformat() if revision is not None else None,
        'channel_revision': channel_revision.isoformat() if channel_revision is not None else None,
        'channel_tested_at': tested.isoformat() if tested is not None else None,
        'channel_ready': bool(channel is not None and channel.enabled and channel.lifecycle_state == 'active'
                              and channel.test_status == 'success' and tested is not None),
    }


def read_local_vault_policies(
    *, instance_id: int, binding_id: int, actor_id: int, page: str, per_page: str
) -> dict[str, Any] | None:
    """Audited exact-instance candidate registry; never destination approval."""
    if not local_reconcile_enabled():
        return None
    try:
        now = datetime.now(UTC)
        eligible = _validated_binding(binding_id, now=now, lock=True)
        if eligible is None or eligible[0].asset_key != str(instance_id) or not _scope(actor_id, instance_id, now=now):
            return None
        binding, source = eligible
        revision = source_revision(binding, source)
        rows = _scoped_policies(instance_id, binding_id)
        if revision is None or rows is None:
            return None
        selected, pagination = paginate_sequence(rows, page=page, per_page=per_page)
        result = {
            'rows': [_policy_projection(row) for row in selected], 'pagination': pagination,
            'binding_id': binding_id, 'source_id': source.id,
            'binding_revision': revision.binding_revision.isoformat(),
            'source_revision': revision.source_revision.isoformat(),
        }
        db.session.add(AuditEvent(
            actor_user_id=actor_id, target_type='integration_instance', target_id=str(instance_id),
            action='vault_provider_routing_candidates_read', summary='Scoped routing candidates reviewed.',
            metadata_json={'instance_id': instance_id, 'binding_id': binding_id},
        ))
        db.session.commit()
        return result
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return None
    finally:
        db.session.rollback()


def disable_local_vault_policy(*, instance_id: int, binding_id: int, actor_id: int, policy_id: int) -> bool:
    """Revoke a candidate without deleting history. Never re-enable an old approval."""
    if not local_reconcile_enabled():
        return False
    try:
        now = datetime.now(UTC)
        eligible = _validated_binding(binding_id, now=now, lock=True)
        if eligible is None or eligible[0].asset_key != str(instance_id) or not _scope(actor_id, instance_id, now=now):
            return False
        rows = _scoped_policies(instance_id, binding_id)
        if rows is None or not any(row.id == policy_id for row in rows):
            return False
        policy = db.session.get(AlertRoutingPolicy, policy_id, populate_existing=True, with_for_update=True)
        if policy is None or not policy.enabled:
            return False
        policy.enabled = False
        policy.updated_by_user_id = actor_id
        db.session.add(AuditEvent(
            actor_user_id=actor_id, target_type='alert_routing_policy', target_id=str(policy_id),
            action='vault_provider_routing_candidate_disabled', summary='Scoped routing candidate disabled.',
            metadata_json={'instance_id': instance_id, 'binding_id': binding_id},
        ))
        db.session.commit()
        return True
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return False
    finally:
        db.session.rollback()
