from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any, NoReturn
from uuid import uuid4

from celery import shared_task
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.common.automation_execution import assert_execution_enabled
from app.extensions.db import db
from app.jobs.execution import JobExecutionContext
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceExecutionJournal
from app.notification_channels.config import notification_delivery_max_attempts
from app.resolver.contracts import VerificationStatus
from app.resolver.notifications import EXECUTION_NOTIFICATION_EVENTS, dispatch_execution_notification
from app.resolver.operations import (
    ResolverOperationalError,
    assert_execution_allowed,
    record_operational_failure,
    record_operational_success,
)
from app.resolver.orchestration import (
    FailureClass,
    Lease,
    OrchestrationError,
    acquire_execution_lease,
    complete_execution_delivery,
    record_execution_failure,
    record_preflight_failure,
    recover_stale_execution_leases,
)
from app.resolver.production_readiness import (
    ProductionReadinessError,
    assert_deployment_policy_allows,
    assert_production_execution_ready,
)
from app.resolver.registry import ResolverRegistry
from app.resolver.service import (
    ResolverDispatchError,
    dispatch_resolver_execution,
    record_verification_failure,
    verify_resolver_execution,
)


@dataclass(frozen=True, slots=True)
class ResolverExecutionLease:
    owner: str
    registry: ResolverRegistry
    secret_key: str
    lease: Lease


def _queue_execution_notification(execution_journal_id: int, event_type: str) -> None:
    try:
        dispatch_resolver_execution_notification.delay(execution_journal_id, event_type)
    except (RuntimeError, ConnectionError, OSError):
        current_app.logger.exception(
            'Could not enqueue Automation Control execution notification %s for journal %s.',
            event_type,
            execution_journal_id,
        )


def _queue_verification(execution_journal_id: int) -> None:
    try:
        verify_authorized_resolution.apply_async(
            kwargs={'execution_journal_id': execution_journal_id},
            countdown=10,
        )
    except (RuntimeError, ConnectionError, OSError):
        current_app.logger.exception(
            'Could not enqueue post-action verification for execution journal %s.',
            execution_journal_id,
        )


@shared_task(
    bind=True,
    name='app.resolver.tasks.dispatch_resolver_execution_notification',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_resolver_execution_notification(self, execution_journal_id: int, event_type: str) -> dict[str, object]:
    """Deliver resolver execution lifecycle events through matching platform channels."""
    if event_type not in EXECUTION_NOTIFICATION_EVENTS:
        return {'status': 'skipped', 'reason': 'unsupported_event_type', 'event_type': event_type}
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        return {
            'status': 'skipped',
            'reason': 'execution_journal_not_found',
            'execution_journal_id': execution_journal_id,
        }
    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '').strip()
    max_attempts = notification_delivery_max_attempts()
    try:
        stats = dispatch_execution_notification(journal, event_type=event_type, base_url=base_url)
    except (SQLAlchemyError, RuntimeError, OSError, ValueError) as exc:
        if self.request.retries < max_attempts - 1:
            countdown = min(30 * (self.request.retries + 1), 120)
            raise self.retry(exc=exc, countdown=countdown, max_retries=max_attempts - 1) from exc
        raise
    if int(stats.get('failed', 0)) > 0 and self.request.retries < max_attempts - 1:
        countdown = min(30 * (self.request.retries + 1), 120)
        raise self.retry(countdown=countdown, max_retries=max_attempts - 1)
    return {'status': 'completed', 'event_type': event_type, **stats}


def _job_context(task_id: str, job_execution_id: int | None) -> JobExecutionContext | None:
    return JobExecutionContext(task_id) if job_execution_id is not None else None


def _fail_missing_journal(
    execution: JobExecutionContext | None,
    message: str,
) -> NoReturn:
    error = RuntimeError(message)
    if execution is not None:
        execution.fail(error, error_code='resolver_journal_missing')
    raise error


def _prepare_execution(
    execution_journal_id: int,
    *,
    owner: str,
) -> ResolverExecutionLease:
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        raise RuntimeError('Execution journal does not exist.')
    assert_execution_enabled()
    decision = journal.decision
    cluster_id = str(decision.cluster_id or '').strip()
    if not cluster_id:
        raise RuntimeError('Resolver execution requires a cluster-scoped decision.')
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise RuntimeError('Resolver target cluster does not exist.')
    registry = current_app.extensions.get('kaori_resolver_registry')
    if not isinstance(registry, ResolverRegistry):
        raise RuntimeError('Resolver registry has not been initialized for this worker process.')
    secret_key = str(current_app.config.get('RESOLVER_TOKEN_SIGNING_KEY') or '')
    if len(secret_key) < 32:
        raise RuntimeError('Resolver token signing key is not configured for this worker process.')

    assert_deployment_policy_allows(
        cluster_id=cluster_id,
        namespace=decision.namespace,
        action_key=decision.action_key,
        registry_fingerprint=str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or ''),
    )
    assert_production_execution_ready(
        cluster_id=cluster_id,
        action_key=decision.action_key,
        cluster_environment=cluster.environment,
    )
    assert_execution_allowed(journal)
    lease = acquire_execution_lease(execution_journal_id, owner=owner)
    # Publish lease ownership before any provider network call. Holding the row
    # lock across external execution hides running state from recovery workers.
    db.session.commit()
    return ResolverExecutionLease(owner, registry, secret_key, lease)


def _persist_preflight_failure(
    execution_journal_id: int,
    *,
    failure_class: FailureClass,
    message: str,
) -> bool:
    db.session.rollback()
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    retryable = bool(
        journal
        and record_preflight_failure(
            journal,
            failure_class=failure_class,
            message=message,
        )
    )
    db.session.commit()
    return retryable


def _raise_retryable_preflight(
    task: Any,
    execution: JobExecutionContext | None,
    execution_journal_id: int,
    exc: ResolverOperationalError,
) -> NoReturn:
    retryable = _persist_preflight_failure(
        execution_journal_id,
        failure_class=FailureClass.RETRYABLE,
        message=str(exc),
    )
    if retryable:
        if execution is not None:
            execution.retrying(message='Resolver preflight will be retried.', error=exc)
        raise task.retry(exc=exc, countdown=30)
    _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
    if execution is not None:
        execution.fail(exc, error_code='resolver_preflight_failed')
    raise exc


def _raise_terminal_preflight(
    execution: JobExecutionContext | None,
    execution_journal_id: int,
    exc: Exception,
) -> NoReturn:
    _persist_preflight_failure(
        execution_journal_id,
        failure_class=FailureClass.TERMINAL,
        message=str(exc),
    )
    _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
    if execution is not None:
        execution.fail(exc, error_code='resolver_preflight_failed')
    raise exc


def _raise_lease_failure(
    execution: JobExecutionContext | None,
    execution_journal_id: int,
    exc: OrchestrationError,
) -> NoReturn:
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is not None and journal.orchestration_status == 'dead_letter':
        db.session.commit()
        _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
    else:
        db.session.rollback()
    if execution is not None:
        execution.fail(exc, error_code='resolver_lease_failed')
    raise exc


def _persist_execution_failure(
    execution_journal_id: int,
    *,
    owner: str,
    failure_class: FailureClass,
    exc: Exception,
) -> bool:
    db.session.rollback()
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None or journal.orchestration_status != 'running':
        return False
    retryable = record_execution_failure(
        journal,
        owner=owner,
        failure_class=failure_class,
        message=str(exc),
    )
    record_operational_failure(journal)
    db.session.commit()
    return retryable


def _execute_with_lease(
    task: Any,
    *,
    execution_journal_id: int,
    token: str,
    actor_user_id: int | None,
    state: ResolverExecutionLease,
    execution: JobExecutionContext | None,
) -> dict[str, object]:
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        _fail_missing_journal(execution, 'Execution journal disappeared after lease acquisition.')
    decision = journal.decision
    try:
        if execution is not None:
            execution.checkpoint(
                current=1,
                total=3,
                percent=45,
                stage='Executing Resolver Action',
                target=f'Execution {execution_journal_id}',
                message='Executing the authorized resolver action.',
            )
        result = dispatch_resolver_execution(
            decision,
            token,
            registry=state.registry,
            secret_key=state.secret_key,
            actor_user_id=actor_user_id,
            actor_permissions={'intelligence.decisions.execute'},
            current_evidence=decision.evidence_json,
            parameters=decision.evidence_json,
        )
        complete_execution_delivery(result, owner=state.owner)
        record_operational_success(result)
        db.session.commit()
        if result.status == 'succeeded':
            _queue_verification(result.id)
        response = {
            'execution_journal_id': result.public_id,
            'status': result.status,
            'orchestration_status': result.orchestration_status,
            'attempt': state.lease.attempt,
        }
        if execution is not None:
            execution.succeed(
                result_summary=response,
                result_type='resolver_execution',
                result_reference=result.public_id,
            )
        return response
    except ResolverDispatchError as exc:
        _persist_execution_failure(
            execution_journal_id,
            owner=state.owner,
            failure_class=FailureClass.TERMINAL,
            exc=exc,
        )
        _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
        if execution is not None:
            execution.fail(exc, error_code='resolver_dispatch_rejected')
        raise
    except ResolverOperationalError as exc:
        retryable = _persist_execution_failure(
            execution_journal_id,
            owner=state.owner,
            failure_class=FailureClass.RETRYABLE,
            exc=exc,
        )
        if retryable:
            if execution is not None:
                execution.retrying(message='Resolver execution will be retried.', error=exc)
            raise task.retry(exc=exc)
        _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
        if execution is not None:
            execution.fail(exc, error_code='resolver_operational_failure')
        raise
    except Exception as exc:
        retryable = _persist_execution_failure(
            execution_journal_id,
            owner=state.owner,
            failure_class=FailureClass.RETRYABLE,
            exc=exc,
        )
        if retryable:
            if execution is not None:
                execution.retrying(message='Resolver execution will be retried.', error=exc)
            raise task.retry(exc=exc)
        _queue_execution_notification(execution_journal_id, 'automation.execution_failed')
        if execution is not None:
            execution.fail(exc, error_code='resolver_execution_failed')
        raise


@shared_task(
    bind=True,
    name='app.resolver.tasks.execute_authorized_resolution',
    acks_late=True,
    reject_on_worker_lost=True,
)
def execute_authorized_resolution(
    self,
    *,
    execution_journal_id: int,
    token: str,
    actor_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, object]:
    """Consume one authorized journal under a distributed execution lease."""
    task_id = str(self.request.id or uuid4())
    owner = f'{socket.gethostname()}:{task_id}'
    execution = _job_context(task_id, job_execution_id)
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        _fail_missing_journal(execution, 'Execution journal does not exist.')
    if execution is not None:
        execution.start(
            message='Validating resolver policy and production readiness.',
            total=3,
            percent=5,
            stage='Validating Resolver Policy',
            target=f'Execution {execution_journal_id}',
        )

    try:
        state = _prepare_execution(execution_journal_id, owner=owner)
    except ResolverOperationalError as exc:
        _raise_retryable_preflight(self, execution, execution_journal_id, exc)
    except ProductionReadinessError as exc:
        _raise_terminal_preflight(execution, execution_journal_id, exc)
    except OrchestrationError as exc:
        _raise_lease_failure(execution, execution_journal_id, exc)
    except RuntimeError as exc:
        _raise_terminal_preflight(execution, execution_journal_id, exc)
    except Exception as exc:
        _raise_terminal_preflight(execution, execution_journal_id, exc)

    _queue_execution_notification(execution_journal_id, 'automation.execution_started')
    return _execute_with_lease(
        self,
        execution_journal_id=execution_journal_id,
        token=token,
        actor_user_id=actor_user_id,
        state=state,
        execution=execution,
    )


@shared_task(
    bind=True,
    name='app.resolver.tasks.verify_authorized_resolution',
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=12,
)
def verify_authorized_resolution(self, *, execution_journal_id: int) -> dict[str, object]:
    """Verify remediation health independently from Kubernetes API mutation success."""
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        return {'status': 'skipped', 'reason': 'execution_journal_not_found'}
    try:
        registry = current_app.extensions.get('kaori_resolver_registry')
        if not isinstance(registry, ResolverRegistry):
            raise RuntimeError('Resolver registry has not been initialized for this verification worker.')
        verification = verify_resolver_execution(journal, registry=registry)
    except (RuntimeError, OSError, ConnectionError) as exc:
        db.session.rollback()
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10) from exc
        summary = 'Post-action verification could not complete because provider health evidence remained unavailable.'
        record_verification_failure(
            journal,
            summary=summary,
            error_code='verification_provider_unavailable',
            evidence={'error_type': type(exc).__name__},
        )
        _queue_execution_notification(execution_journal_id, 'automation.verification_failed')
        return {'status': 'failed', 'reason': 'verification_provider_unavailable'}

    if verification.status is VerificationStatus.PENDING:
        if self.request.retries >= self.max_retries:
            summary = 'Post-action verification timed out before the workload became healthy.'
            record_verification_failure(
                journal,
                summary=summary,
                error_code='verification_timeout',
                evidence=verification.evidence,
            )
            _queue_execution_notification(execution_journal_id, 'automation.verification_failed')
            return {'status': 'failed', 'reason': 'verification_timeout'}
        raise self.retry(countdown=10)
    if verification.status is VerificationStatus.FAILED:
        _queue_execution_notification(execution_journal_id, 'automation.verification_failed')
        return {'status': 'failed', 'summary': verification.summary}
    _queue_execution_notification(execution_journal_id, 'automation.execution_completed')
    return {'status': 'verified', 'summary': verification.summary}


@shared_task(
    name='app.resolver.tasks.reconcile_stale_execution_leases',
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_stale_execution_leases() -> dict[str, int]:
    """Recover resolver executions abandoned by stopped or lost workers."""
    return recover_stale_execution_leases()
