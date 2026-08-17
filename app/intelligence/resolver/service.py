from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.intelligence.resolver.contracts import (
    ResolverContext,
    ResolverResult,
    ResolverResultStatus,
    VerificationResult,
    VerificationStatus,
    build_idempotency_key,
)
from app.intelligence.resolver.registry import ResolverRegistry
from app.intelligence.workflow import (
    EXECUTE_PERMISSION,
    DecisionWorkflowError,
    consume_execution_token,
)
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceDecision, IntelligenceExecutionJournal


class ResolverDispatchError(RuntimeError):
    """Raised when resolver dispatch cannot safely proceed."""


def dispatch_resolver_execution(
    record: IntelligenceDecision,
    token: str,
    *,
    registry: ResolverRegistry,
    secret_key: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    current_evidence: Mapping[str, Any] | None = None,
    parameters: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> IntelligenceExecutionJournal:
    if EXECUTE_PERMISSION not in actor_permissions:
        raise ResolverDispatchError(f'Missing required permission: {EXECUTE_PERMISSION}.')

    adapter = registry.resolve(record.action_key)
    issued_journal = _find_authorized_journal(record)
    context = _resolver_context(record, issued_journal, parameters=parameters or {})

    dry_run = adapter.dry_run(context)
    issued_journal.result_json = {
        'dry_run': {
            'allowed': dry_run.allowed,
            'summary': dry_run.summary,
            'planned_changes': [dict(item) for item in dry_run.planned_changes],
            'rollback_plan': dict(dry_run.rollback_plan) if dry_run.rollback_plan else None,
        },
        'idempotency_key': context.idempotency_key,
    }
    if not dry_run.allowed:
        issued_journal.status = 'canceled'
        issued_journal.completed_at = now or datetime.now(UTC)
        issued_journal.error_message = dry_run.summary
        _audit(record, actor_user_id, 'intelligence.execution.dry_run_blocked', dry_run.summary)
        db.session.commit()
        raise ResolverDispatchError(f'Resolver dry-run blocked execution: {dry_run.summary}')

    try:
        journal = consume_execution_token(
            record,
            token,
            secret_key=secret_key,
            actor_user_id=actor_user_id,
            actor_permissions=actor_permissions,
            current_evidence=current_evidence,
            now=now,
        )
    except DecisionWorkflowError as exc:
        db.session.rollback()
        raise ResolverDispatchError(str(exc)) from exc

    try:
        result = adapter.execute(context, dry_run)
    except Exception as exc:
        journal.status = 'failed'
        journal.completed_at = now or datetime.now(UTC)
        journal.error_message = str(exc)
        journal.result_json = {**(journal.result_json or {}), 'retryable': False}
        _audit(record, actor_user_id, 'intelligence.execution.failed', str(exc))
        db.session.commit()
        raise ResolverDispatchError('Resolver execution failed.') from exc

    _record_result(journal, result, now=now)
    _audit(record, actor_user_id, f'intelligence.execution.{journal.status}', result.summary)
    db.session.commit()
    return journal


def verify_resolver_execution(
    journal: IntelligenceExecutionJournal,
    *,
    registry: ResolverRegistry,
) -> VerificationResult:
    if journal.status != 'succeeded':
        raise ResolverDispatchError('Only successful resolver execution can enter post-action verification.')
    payload = dict(journal.result_json or {})
    execution = dict(payload.get('execution') or {})
    execution_result = execution.get('result')
    if not isinstance(execution_result, Mapping):
        raise ResolverDispatchError('Execution result evidence is unavailable for verification.')
    try:
        status = ResolverResultStatus(str(execution.get('status') or ''))
    except ValueError as exc:
        raise ResolverDispatchError('Persisted resolver result status is invalid.') from exc
    result = ResolverResult(
        status=status,
        summary=str(execution.get('summary') or ''),
        result=dict(execution_result),
        rollback_reference=str(execution.get('rollback_reference') or '') or None,
        retryable=bool(execution.get('retryable')),
    )
    decision = journal.decision
    adapter = registry.resolve(decision.action_key)
    verification = adapter.verify(
        _resolver_context(decision, journal, parameters=decision.evidence_json),
        result,
    )
    payload['verification'] = {
        'status': verification.status.value,
        'summary': verification.summary,
        'evidence': dict(verification.evidence),
    }
    journal.result_json = payload
    if verification.status is VerificationStatus.FAILED:
        journal.last_error_code = 'verification_failed'
        journal.error_message = verification.summary
    elif verification.status is VerificationStatus.VERIFIED:
        journal.last_error_code = None
        journal.error_message = None
    if verification.status is not VerificationStatus.PENDING:
        _audit(
            decision,
            journal.requested_by_user_id,
            f'intelligence.execution.verification_{verification.status.value}',
            verification.summary,
        )
    db.session.commit()
    return verification


def record_verification_failure(
    journal: IntelligenceExecutionJournal,
    *,
    summary: str,
    error_code: str = 'verification_failed',
    evidence: Mapping[str, Any] | None = None,
) -> None:
    """Persist one terminal remediation-verification failure with audit evidence."""
    if journal.status != 'succeeded':
        raise ResolverDispatchError('Only successful resolver execution can fail post-action verification.')
    payload = dict(journal.result_json or {})
    payload['verification'] = {
        'status': VerificationStatus.FAILED.value,
        'summary': summary,
        'evidence': dict(evidence or {}),
    }
    journal.result_json = payload
    journal.last_error_code = error_code
    journal.error_message = summary
    _audit(
        journal.decision,
        journal.requested_by_user_id,
        'intelligence.execution.verification_failed',
        summary,
    )
    db.session.commit()


def _resolver_context(
    record: IntelligenceDecision,
    journal: IntelligenceExecutionJournal,
    *,
    parameters: Mapping[str, Any],
) -> ResolverContext:
    return ResolverContext(
        decision_id=record.public_id,
        journal_id=journal.public_id,
        action_key=record.action_key,
        evidence_hash=record.evidence_hash,
        idempotency_key=build_idempotency_key(
            decision_id=record.public_id,
            action_key=record.action_key,
            evidence_hash=record.evidence_hash,
        ),
        cluster_id=record.cluster_id,
        namespace=record.namespace,
        parameters=parameters,
    )


def _find_authorized_journal(record: IntelligenceDecision) -> IntelligenceExecutionJournal:
    journal = (
        IntelligenceExecutionJournal.query.filter_by(decision_id=record.id, status='authorized')
        .order_by(IntelligenceExecutionJournal.id.desc())
        .first()
    )
    if journal is None:
        raise ResolverDispatchError('No active execution authorization exists for this decision.')
    return journal


def _record_result(
    journal: IntelligenceExecutionJournal,
    result: ResolverResult,
    *,
    now: datetime | None,
) -> None:
    if result.status in {ResolverResultStatus.SUCCEEDED, ResolverResultStatus.NOOP}:
        journal.status = 'succeeded'
    else:
        journal.status = 'failed'
    journal.completed_at = now or datetime.now(UTC)
    journal.error_message = None if journal.status == 'succeeded' else result.summary
    payload = {
        **(journal.result_json or {}),
        'execution': {
            'status': result.status.value,
            'summary': result.summary,
            'result': dict(result.result),
            'rollback_reference': result.rollback_reference,
            'retryable': result.retryable,
        },
    }
    if journal.status == 'succeeded':
        payload['verification'] = {
            'status': VerificationStatus.PENDING.value,
            'summary': 'Post-action remediation verification is pending.',
            'evidence': {},
        }
    journal.result_json = payload


def _audit(
    record: IntelligenceDecision,
    actor_user_id: int | None,
    action: str,
    summary: str,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'intelligence_decision'
    event.target_id = record.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {'action_key': record.action_key, 'evidence_hash': record.evidence_hash}
    db.session.add(event)
