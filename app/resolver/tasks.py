from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any, NoReturn
from uuid import uuid4

from celery import shared_task
from flask import current_app

from app.extensions.db import db
from app.jobs.execution import JobExecutionContext
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceExecutionJournal
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
from app.resolver.service import ResolverDispatchError, dispatch_resolver_execution


@dataclass(frozen=True, slots=True)
class ResolverExecutionLease:
    owner: str
    registry: ResolverRegistry
    secret_key: str
    lease: Lease


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
            execution.checkpoint(current=1, total=3, message='Executing the authorized resolver action.')
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
        execution.start(message='Validating resolver policy and production readiness.', total=3)

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
        db.session.rollback()
        if execution is not None:
            execution.fail(exc, error_code='resolver_preflight_unexpected')
        raise

    return _execute_with_lease(
        self,
        execution_journal_id=execution_journal_id,
        token=token,
        actor_user_id=actor_user_id,
        state=state,
        execution=execution,
    )


@shared_task(
    name='app.resolver.tasks.reconcile_stale_execution_leases',
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_stale_execution_leases() -> dict[str, int]:
    """Recover resolver executions abandoned by stopped or lost workers."""
    return recover_stale_execution_leases()
