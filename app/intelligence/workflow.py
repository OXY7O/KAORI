from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.common.automation_execution import assert_execution_enabled, build_idempotency_key
from app.extensions.db import db
from app.intelligence.decision import (
    DecisionError,
    DecisionPolicy,
    DecisionSnapshot,
    PolicyOutcome,
    authorize_execution,
    issue_execution_token,
)
from app.models.audit import AuditEvent
from app.models.intelligence import (
    IntelligenceDecision,
    IntelligenceDecisionApproval,
    IntelligenceExecutionJournal,
)

CREATE_PERMISSION = 'intelligence.decisions.create'
APPROVE_PERMISSION = 'intelligence.decisions.approve'
EXECUTE_PERMISSION = 'intelligence.decisions.execute'
VIEW_PERMISSION = 'intelligence.decisions.view'


class DecisionWorkflowError(RuntimeError):
    """Raised when a persisted decision workflow transition is invalid."""


def _now() -> datetime:
    return datetime.now(UTC)


def _require_permission(permissions: Collection[str], permission: str) -> None:
    if permission not in permissions:
        raise DecisionWorkflowError(f'Missing required permission: {permission}.')


def persist_decision(
    snapshot: DecisionSnapshot,
    *,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
) -> IntelligenceDecision:
    _require_permission(actor_permissions, CREATE_PERMISSION)
    if snapshot.policy.outcome is PolicyOutcome.BLOCKED:
        raise DecisionWorkflowError('Blocked decisions cannot enter the execution workflow.')

    existing = IntelligenceDecision.query.filter_by(public_id=snapshot.decision_id).first()
    if existing is not None:
        if existing.evidence_hash != snapshot.evidence_hash:
            raise DecisionWorkflowError('Decision identifier already exists with different evidence.')
        return existing

    payload = snapshot.to_payload()
    record = IntelligenceDecision()
    record.public_id = snapshot.decision_id
    record.recommendation_key = snapshot.recommendation_key
    record.rule_key = snapshot.rule_key
    record.rule_version = snapshot.rule_version
    record.knowledge_version = snapshot.knowledge_version
    record.runbook_key = snapshot.runbook_key
    record.runbook_version = snapshot.runbook_version
    record.runbook_content_hash = snapshot.runbook_content_hash
    if snapshot.runbook_revision_id is not None:
        from app.models.knowledge import KnowledgeRunbookRevision

        revision = KnowledgeRunbookRevision.query.filter_by(public_id=snapshot.runbook_revision_id).first()
        if revision is None or revision.publication_status != 'published':
            raise DecisionWorkflowError('Decision requires an active published runbook revision.')
        if revision.content_hash != snapshot.runbook_content_hash:
            raise DecisionWorkflowError('Runbook revision content hash does not match decision snapshot.')
        record.runbook_revision_id = revision.id
    record.action_key = snapshot.action_key
    record.cluster_id = snapshot.cluster_id
    record.namespace = snapshot.namespace
    record.severity = snapshot.severity
    record.evidence_json = payload['evidence']
    record.evidence_hash = snapshot.evidence_hash
    record.inventory_generation = snapshot.inventory_generation
    record.alert_fingerprint = snapshot.alert_fingerprint
    record.policy_outcome = snapshot.policy.outcome.value
    record.policy_reason = snapshot.policy.reason
    record.approval_required = snapshot.policy.approval_required
    record.workflow_status = 'pending_approval' if snapshot.policy.approval_required else 'ready'
    record.snapshot_json = payload
    record.created_by_user_id = actor_user_id
    record.created_at = snapshot.created_at
    record.expires_at = snapshot.expires_at
    db.session.add(record)
    _audit(
        actor_user_id=actor_user_id,
        target_id=snapshot.decision_id,
        action='intelligence.decision.created',
        summary='KAORI decision snapshot created.',
        metadata={'policy_outcome': record.policy_outcome, 'evidence_hash': record.evidence_hash},
    )
    db.session.commit()
    return record


def approve_decision(
    record: IntelligenceDecision,
    *,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    reason: str | None = None,
    now: datetime | None = None,
) -> IntelligenceDecisionApproval:
    return _record_approval(
        record,
        outcome='approved',
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        reason=reason,
        now=now,
    )


def reject_decision(
    record: IntelligenceDecision,
    *,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    reason: str,
    now: datetime | None = None,
) -> IntelligenceDecisionApproval:
    if not reason.strip():
        raise DecisionWorkflowError('Decision rejection requires a reason.')
    return _record_approval(
        record,
        outcome='rejected',
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        reason=reason,
        now=now,
    )


def _record_approval(
    record: IntelligenceDecision,
    *,
    outcome: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    reason: str | None,
    now: datetime | None,
) -> IntelligenceDecisionApproval:
    _require_permission(actor_permissions, APPROVE_PERMISSION)
    checked_at = now or _now()
    _assert_active(record, checked_at)
    if (
        record.approval_required
        and actor_user_id is not None
        and record.created_by_user_id is not None
        and actor_user_id == record.created_by_user_id
    ):
        raise DecisionWorkflowError(
            'Approval-required decisions enforce maker-checker separation; the decision creator cannot approve or reject their own decision.'
        )
    if record.workflow_status not in {'pending_approval', 'ready'}:
        raise DecisionWorkflowError(f'Decision cannot be {outcome} from {record.workflow_status}.')

    approval = IntelligenceDecisionApproval()
    approval.decision_id = record.id
    approval.outcome = outcome
    approval.reason = reason.strip() if reason else None
    approval.actor_user_id = actor_user_id
    approval.evidence_hash = record.evidence_hash
    approval.created_at = checked_at
    record.workflow_status = outcome
    db.session.add(approval)
    _audit(
        actor_user_id=actor_user_id,
        target_id=record.public_id,
        action=f'intelligence.decision.{outcome}',
        summary=f'KAORI decision {outcome}.',
        metadata={'reason': approval.reason, 'evidence_hash': record.evidence_hash},
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DecisionWorkflowError('Decision already has an approval outcome.') from exc
    return approval


def issue_persisted_execution_token(
    record: IntelligenceDecision,
    *,
    secret_key: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    now: datetime | None = None,
) -> tuple[str, IntelligenceExecutionJournal]:
    assert_execution_enabled()
    _require_permission(actor_permissions, EXECUTE_PERMISSION)
    issued_at = now or _now()
    _assert_active(record, issued_at)
    if record.workflow_status == 'rejected':
        raise DecisionWorkflowError('Rejected decisions cannot be executed.')
    if record.approval_required and record.workflow_status != 'approved':
        raise DecisionWorkflowError('Decision requires approval before token issuance.')
    if record.workflow_status not in {'ready', 'approved'}:
        raise DecisionWorkflowError(f'Decision cannot issue a token from {record.workflow_status}.')

    snapshot = snapshot_from_record(record)
    token = issue_execution_token(
        snapshot,
        secret_key=secret_key,
        approved=record.workflow_status == 'approved',
        now=issued_at,
    )
    authorization = authorize_execution(snapshot, token, secret_key=secret_key, now=issued_at)
    journal = IntelligenceExecutionJournal()
    journal.decision_id = record.id
    journal.token_nonce_hash = _nonce_hash(authorization.nonce)
    journal.action_key = authorization.action_key
    journal.evidence_hash = authorization.evidence_hash
    journal.idempotency_key = build_idempotency_key(
        decision_id=record.public_id,
        action_key=authorization.action_key,
        evidence_hash=authorization.evidence_hash,
    )
    journal.status = 'authorized'
    journal.requested_by_user_id = actor_user_id
    journal.issued_at = authorization.issued_at
    journal.expires_at = authorization.expires_at
    db.session.add(journal)
    try:
        db.session.flush()
        _audit(
            actor_user_id=actor_user_id,
            target_id=record.public_id,
            action='intelligence.execution.authorized',
            summary='One-time execution authorization issued.',
            metadata={'journal_public_id': journal.public_id, 'evidence_hash': journal.evidence_hash},
        )
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DecisionWorkflowError(
            'This immutable decision already has an execution authorization; fresh evidence and a new decision are required.'
        ) from exc
    return token, journal


def consume_execution_token(
    record: IntelligenceDecision,
    token: str,
    *,
    secret_key: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    current_evidence: Mapping[str, Any] | None = None,
    resolver_job_id: int | None = None,
    now: datetime | None = None,
) -> IntelligenceExecutionJournal:
    _require_permission(actor_permissions, EXECUTE_PERMISSION)
    checked_at = now or _now()
    _assert_active(record, checked_at)
    snapshot = snapshot_from_record(record)
    try:
        authorization = authorize_execution(
            snapshot,
            token,
            secret_key=secret_key,
            current_evidence=current_evidence,
            now=checked_at,
        )
    except DecisionError as exc:
        raise DecisionWorkflowError(str(exc)) from exc

    journal = (
        IntelligenceExecutionJournal.query.filter_by(
            decision_id=record.id,
            token_nonce_hash=_nonce_hash(authorization.nonce),
        )
        .with_for_update()
        .first()
    )
    if journal is None:
        raise DecisionWorkflowError('Execution token was not issued by the persisted workflow.')
    if journal.status != 'authorized' or journal.consumed_at is not None:
        raise DecisionWorkflowError('Execution token has already been consumed.')

    journal.status = 'dispatched'
    journal.consumed_at = checked_at
    journal.resolver_job_id = resolver_job_id
    record.workflow_status = 'dispatched'
    _audit(
        actor_user_id=actor_user_id,
        target_id=record.public_id,
        action='intelligence.execution.dispatched',
        summary='Approved KAORI decision dispatched to the resolver boundary.',
        metadata={'journal_public_id': journal.public_id, 'resolver_job_id': resolver_job_id},
    )
    db.session.commit()
    return journal


def expire_stale_decisions(*, now: datetime | None = None) -> int:
    checked_at = now or _now()
    rows = IntelligenceDecision.query.filter(
        IntelligenceDecision.workflow_status.in_(('ready', 'pending_approval', 'approved')),
        IntelligenceDecision.expires_at <= checked_at,
    ).all()
    for row in rows:
        row.workflow_status = 'expired'
        _audit(
            actor_user_id=None,
            target_id=row.public_id,
            action='intelligence.decision.expired',
            summary='KAORI decision expired before execution dispatch.',
            metadata={'evidence_hash': row.evidence_hash},
        )
    db.session.commit()
    return len(rows)


def snapshot_from_record(record: IntelligenceDecision) -> DecisionSnapshot:
    payload = record.snapshot_json
    if not isinstance(payload, dict) or payload.get('evidence_hash') != record.evidence_hash:
        raise DecisionWorkflowError('Persisted decision snapshot failed integrity validation.')
    try:
        return DecisionSnapshot(
            decision_id=record.public_id,
            recommendation_key=record.recommendation_key,
            rule_key=record.rule_key,
            rule_version=record.rule_version,
            knowledge_version=record.knowledge_version,
            runbook_key=record.runbook_key,
            runbook_revision_id=record.runbook_revision.public_id if record.runbook_revision else None,
            runbook_version=record.runbook_version,
            runbook_content_hash=record.runbook_content_hash,
            action_key=record.action_key,
            cluster_id=record.cluster_id,
            namespace=record.namespace,
            severity=record.severity,
            evidence=record.evidence_json,
            evidence_hash=record.evidence_hash,
            inventory_generation=record.inventory_generation,
            alert_fingerprint=record.alert_fingerprint,
            policy=DecisionPolicy(
                outcome=PolicyOutcome(record.policy_outcome),
                reason=record.policy_reason,
                approval_required=record.approval_required,
            ),
            created_at=_aware(record.created_at),
            expires_at=_aware(record.expires_at),
        )
    except (TypeError, ValueError) as exc:
        raise DecisionWorkflowError('Persisted decision snapshot is invalid.') from exc


def _assert_active(record: IntelligenceDecision, now: datetime) -> None:
    if now.tzinfo is None:
        raise DecisionWorkflowError('Workflow timestamp must be timezone-aware.')
    if now >= _aware(record.expires_at):
        record.workflow_status = 'expired'
        db.session.flush()
        raise DecisionWorkflowError('Decision has expired.')


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode('utf-8')).hexdigest()


def _audit(
    *,
    actor_user_id: int | None,
    target_id: str,
    action: str,
    summary: str,
    metadata: dict[str, Any] | None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'intelligence_decision'
    event.target_id = target_id
    event.action = action
    event.summary = summary
    event.metadata_json = metadata
    db.session.add(event)
