from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from typing import Any

from app.extensions import db
from app.intelligence.workflow import (
    EXECUTE_PERMISSION,
    DecisionWorkflowError,
    consume_execution_token,
)
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceDecision, IntelligenceExecutionJournal
from app.resolver.contracts import (
    ResolverContext,
    ResolverResult,
    ResolverResultStatus,
    build_idempotency_key,
)
from app.resolver.registry import ResolverRegistry


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
    context = ResolverContext(
        decision_id=record.public_id,
        journal_id=issued_journal.public_id,
        action_key=record.action_key,
        evidence_hash=record.evidence_hash,
        idempotency_key=build_idempotency_key(
            decision_id=record.public_id,
            action_key=record.action_key,
            evidence_hash=record.evidence_hash,
        ),
        cluster_id=record.cluster_id,
        namespace=record.namespace,
        parameters=parameters or {},
    )

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
    journal.result_json = {
        **(journal.result_json or {}),
        'execution': {
            'status': result.status.value,
            'summary': result.summary,
            'result': dict(result.result),
            'rollback_reference': result.rollback_reference,
            'retryable': result.retryable,
        },
    }


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
