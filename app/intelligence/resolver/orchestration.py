from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from flask import current_app, has_app_context

from app.extensions.db import db
from app.intelligence.resolver.contracts import build_idempotency_key
from app.models.audit import AuditEvent
from app.models.intelligence import IntelligenceExecutionJournal
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job

RESOLVER_QUEUE = 'resolver-execution'
DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3


class OrchestrationError(RuntimeError):
    """Raised when distributed execution ownership cannot be established safely."""


class FailureClass(StrEnum):
    RETRYABLE = 'retryable'
    TERMINAL = 'terminal'
    TIMEOUT = 'timeout'
    WORKER_LOST = 'worker_lost'


@dataclass(frozen=True, slots=True)
class Lease:
    journal_id: int
    owner: str
    expires_at: datetime
    attempt: int


def resolver_execution_queue_name() -> str:
    if has_app_context():
        configured = str(current_app.config.get('RESOLVER_EXECUTION_CELERY_QUEUE') or '').strip()
        if configured:
            return configured
    return RESOLVER_QUEUE


def prepare_execution_delivery(
    journal: IntelligenceExecutionJournal,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    queue_name: str | None = None,
) -> bool:
    """Prepare one canonical Celery delivery; return False for an existing delivery."""
    decision = journal.decision
    key = build_idempotency_key(
        decision_id=decision.public_id,
        action_key=journal.action_key,
        evidence_hash=journal.evidence_hash,
    )
    duplicate = IntelligenceExecutionJournal.query.filter(
        IntelligenceExecutionJournal.id != journal.id,
        IntelligenceExecutionJournal.idempotency_key == key,
        IntelligenceExecutionJournal.orchestration_status.in_(('queued', 'running', 'retry_wait', 'completed')),
    ).first()
    if duplicate is not None:
        return False
    if journal.orchestration_status not in {'pending', 'retry_wait'}:
        return False
    journal.idempotency_key = key
    journal.queue_name = str(queue_name or resolver_execution_queue_name()).strip() or RESOLVER_QUEUE
    journal.max_attempts = max(1, max_attempts)
    journal.celery_task_id = journal.celery_task_id or str(uuid4())
    journal.orchestration_status = 'queued'
    journal.next_retry_at = None
    db.session.flush()
    return True


def enqueue_execution_delivery(
    journal: IntelligenceExecutionJournal,
    *,
    task: Any,
    token: str,
    actor_user_id: int | None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    queue_name: str | None = None,
) -> tuple[Any, bool]:
    """Dispatch through KAORI's canonical JobExecution foundation exactly once."""
    if not prepare_execution_delivery(journal, max_attempts=max_attempts, queue_name=queue_name):
        if journal.resolver_job_id is None:
            raise OrchestrationError('Execution delivery already exists without a canonical job reference.')
        return journal.resolver_job_id, False
    decision = journal.decision
    try:
        job, created = enqueue_canonical_job(
            task=task,
            task_kwargs={
                'execution_journal_id': journal.id,
                'token': token,
                'actor_user_id': actor_user_id,
            },
            job_type='resolver_execution',
            operation=journal.action_key,
            queue_name=journal.queue_name,
            workload_class='mutation',
            requested_by_user_id=actor_user_id,
            resource_group=f'resolver:{decision.cluster_id or "global"}',
            parameters={
                'decision_id': decision.public_id,
                'execution_journal_id': journal.public_id,
                'evidence_hash': journal.evidence_hash,
            },
            payload=None,
            integration_type='resolver',
            integration_instance_id=None,
            scope_type='cluster' if decision.cluster_id else 'global',
            scope_key=decision.cluster_id,
            max_attempts=journal.max_attempts,
        )
    except Exception as exc:
        # Authorization is one-time and the raw token is never persisted. If
        # canonical delivery fails, terminalize this journal rather than leaving
        # an orphan that cannot be replayed safely. A fresh decision is required.
        journal.status = 'canceled'
        journal.orchestration_status = 'dead_letter'
        journal.celery_task_id = None
        journal.resolver_job_id = None
        journal.last_error_code = 'dispatch_failed'
        journal.error_message = str(exc)
        journal.next_retry_at = None
        journal.completed_at = datetime.now(UTC)
        _audit(journal, 'intelligence.execution.dispatch_failed')
        db.session.commit()
        raise
    journal.resolver_job_id = job.id
    journal.celery_task_id = job.celery_task_id
    db.session.commit()
    return job, created


def acquire_execution_lease(
    journal_id: int,
    *,
    owner: str,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Lease:
    current = now or datetime.now(UTC)
    journal = db.session.get(IntelligenceExecutionJournal, journal_id, with_for_update=True)
    if journal is None:
        raise OrchestrationError('Execution journal does not exist.')
    if journal.orchestration_status not in {'queued', 'retry_wait', 'running'}:
        raise OrchestrationError('Execution journal is not eligible for worker acquisition.')
    if journal.next_retry_at and _aware(journal.next_retry_at) > current:
        raise OrchestrationError('Execution retry is not due yet.')
    active_lease = journal.lease_expires_at and _aware(journal.lease_expires_at) > current
    if active_lease and journal.lease_owner != owner:
        raise OrchestrationError('Execution journal is leased by another worker.')
    if journal.attempt_count >= journal.max_attempts:
        journal.orchestration_status = 'dead_letter'
        db.session.flush()
        raise OrchestrationError('Execution journal exhausted its retry budget.')
    journal.attempt_count += 1
    journal.orchestration_status = 'running'
    journal.lease_owner = owner
    journal.lease_acquired_at = current
    journal.last_heartbeat_at = current
    expires_at = current + timedelta(seconds=max(1, lease_seconds))
    journal.lease_expires_at = expires_at
    db.session.flush()
    return Lease(journal.id, owner, expires_at, journal.attempt_count)


def heartbeat_execution_lease(
    journal: IntelligenceExecutionJournal,
    *,
    owner: str,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    current = now or datetime.now(UTC)
    if journal.orchestration_status != 'running' or journal.lease_owner != owner:
        raise OrchestrationError('Worker does not own the active execution lease.')
    if journal.lease_expires_at and _aware(journal.lease_expires_at) <= current:
        raise OrchestrationError('Execution lease has expired.')
    journal.last_heartbeat_at = current
    journal.lease_expires_at = current + timedelta(seconds=max(1, lease_seconds))
    db.session.flush()


def complete_execution_delivery(journal: IntelligenceExecutionJournal, *, owner: str) -> None:
    _require_owner(journal, owner)
    journal.orchestration_status = 'completed'
    _release_lease(journal)
    db.session.flush()


def record_execution_failure(
    journal: IntelligenceExecutionJournal,
    *,
    owner: str,
    failure_class: FailureClass,
    message: str,
    now: datetime | None = None,
) -> bool:
    """Record failure and return True only when another attempt may be scheduled."""
    _require_owner(journal, owner)
    current = now or datetime.now(UTC)
    journal.last_error_code = failure_class.value
    journal.error_message = message
    retryable = failure_class in {
        FailureClass.RETRYABLE,
        FailureClass.TIMEOUT,
        FailureClass.WORKER_LOST,
    }
    may_retry = retryable and journal.attempt_count < journal.max_attempts
    if may_retry:
        delay = min(900, 30 * (2 ** max(0, journal.attempt_count - 1)))
        journal.orchestration_status = 'retry_wait'
        journal.next_retry_at = current + timedelta(seconds=delay)
    else:
        journal.orchestration_status = 'dead_letter'
        journal.completed_at = current
    _release_lease(journal)
    db.session.flush()
    return may_retry


def record_preflight_failure(
    journal: IntelligenceExecutionJournal,
    *,
    failure_class: FailureClass,
    message: str,
    now: datetime | None = None,
) -> bool:
    """Persist a worker failure that occurs before execution lease acquisition."""
    if journal.orchestration_status not in {'queued', 'retry_wait'}:
        return False
    current = now or datetime.now(UTC)
    journal.attempt_count += 1
    journal.last_error_code = failure_class.value
    journal.error_message = message
    may_retry = failure_class == FailureClass.RETRYABLE and journal.attempt_count < journal.max_attempts
    if may_retry:
        journal.orchestration_status = 'retry_wait'
        journal.next_retry_at = current + timedelta(seconds=30)
    else:
        journal.orchestration_status = 'dead_letter'
        journal.completed_at = current
        journal.next_retry_at = None
    _release_lease(journal)
    _audit(journal, 'intelligence.execution.preflight_failed')
    db.session.flush()
    return may_retry


def expire_stale_execution_authorizations(*, now: datetime | None = None) -> int:
    """Terminalize unused one-time authorizations after their signed TTL expires."""
    current = now or datetime.now(UTC)
    rows = (
        IntelligenceExecutionJournal.query.filter(
            IntelligenceExecutionJournal.status == 'authorized',
            IntelligenceExecutionJournal.expires_at <= current,
            IntelligenceExecutionJournal.orchestration_status.in_(('pending', 'queued', 'retry_wait')),
        )
        .with_for_update(skip_locked=True)
        .all()
    )
    for journal in rows:
        journal.status = 'canceled'
        journal.orchestration_status = 'dead_letter'
        journal.last_error_code = 'authorization_expired'
        journal.error_message = 'One-time execution authorization expired before safe token consumption.'
        journal.next_retry_at = None
        journal.completed_at = current
        _release_lease(journal)
        _audit(journal, 'intelligence.execution.authorization_expired')
    db.session.commit()
    return len(rows)


def recover_stale_execution_leases(*, now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(UTC)
    stale = (
        IntelligenceExecutionJournal.query.filter(
            IntelligenceExecutionJournal.orchestration_status == 'running',
            IntelligenceExecutionJournal.lease_expires_at.is_not(None),
            IntelligenceExecutionJournal.lease_expires_at <= current,
        )
        .with_for_update(skip_locked=True)
        .all()
    )
    recovered = 0
    dead_lettered = 0
    for journal in stale:
        token_consumed = journal.consumed_at is not None or journal.status != 'authorized'
        if token_consumed:
            # A consumed authorization is deliberately never replayed after worker loss.
            # The mutation outcome may be indeterminate, so retain immutable evidence for review.
            journal.last_error_code = 'worker_lost_after_token_consumed'
            journal.error_message = (
                'Execution worker was lost after the one-time authorization was consumed; automatic replay is blocked.'
            )
            journal.orchestration_status = 'dead_letter'
            journal.completed_at = current
            journal.next_retry_at = None
            dead_lettered += 1
        elif journal.attempt_count < journal.max_attempts:
            journal.last_error_code = FailureClass.WORKER_LOST.value
            journal.error_message = 'Execution lease expired before token consumption; delivery may be retried safely.'
            journal.orchestration_status = 'retry_wait'
            journal.next_retry_at = current
            recovered += 1
        else:
            journal.last_error_code = FailureClass.WORKER_LOST.value
            journal.error_message = 'Execution lease expired and exhausted its retry budget.'
            journal.orchestration_status = 'dead_letter'
            journal.completed_at = current
            journal.next_retry_at = None
            dead_lettered += 1
        _release_lease(journal)
        _audit(journal, 'intelligence.execution.lease_recovered')
    db.session.commit()
    return {'recovered': recovered, 'dead_lettered': dead_lettered}


def _require_owner(journal: IntelligenceExecutionJournal, owner: str) -> None:
    if journal.orchestration_status != 'running' or journal.lease_owner != owner:
        raise OrchestrationError('Worker does not own the active execution lease.')


def _release_lease(journal: IntelligenceExecutionJournal) -> None:
    journal.lease_owner = None
    journal.lease_acquired_at = None
    journal.lease_expires_at = None
    journal.last_heartbeat_at = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _audit(journal: IntelligenceExecutionJournal, action: str) -> None:
    event = AuditEvent()
    event.actor_user_id = journal.requested_by_user_id
    event.target_type = 'intelligence_execution_journal'
    event.target_id = journal.public_id
    event.action = action
    event.summary = journal.error_message or action
    event.metadata_json = {
        'attempt_count': journal.attempt_count,
        'last_error_code': journal.last_error_code,
    }
    db.session.add(event)
