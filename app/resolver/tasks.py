from __future__ import annotations

import socket
from uuid import uuid4

from celery import shared_task
from flask import current_app

from app.extensions import db
from app.resolver.registry import ResolverRegistry
from app.models.cluster import Cluster
from app.models.intelligence import IntelligenceExecutionJournal
from app.resolver.orchestration import (
    FailureClass,
    acquire_execution_lease,
    complete_execution_delivery,
    record_execution_failure,
    recover_stale_execution_leases,
)
from app.resolver.service import ResolverDispatchError, dispatch_resolver_execution
from app.resolver.operations import (
    ResolverOperationalError,
    assert_execution_allowed,
    record_operational_failure,
    record_operational_success,
)
from app.resolver.production_readiness import (
    assert_deployment_policy_allows,
    assert_production_execution_ready,
)


@shared_task(
    bind=True,
    name='app.resolver.tasks.execute_authorized_resolution',
    acks_late=True,
    reject_on_worker_lost=True,
    queue='resolver-execution',
)
def execute_authorized_resolution(
    self,
    *,
    execution_journal_id: int,
    token: str,
    secret_key: str,
    actor_user_id: int | None,
) -> dict[str, object]:
    """Consume one authorized journal under a distributed execution lease."""
    owner = f'{socket.gethostname()}:{self.request.id or uuid4()}'
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
    journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
    if journal is None:
        raise RuntimeError('Execution journal disappeared after lease acquisition.')
    decision = journal.decision
    try:
        result = dispatch_resolver_execution(
            decision,
            token,
            registry=registry,
            secret_key=secret_key,
            actor_user_id=actor_user_id,
            actor_permissions={'intelligence.decisions.execute'},
            current_evidence=decision.evidence_json,
            parameters=decision.evidence_json,
        )
        complete_execution_delivery(result, owner=owner)
        record_operational_success(result)
        db.session.commit()
        return {
            'execution_journal_id': result.public_id,
            'status': result.status,
            'orchestration_status': result.orchestration_status,
            'attempt': lease.attempt,
        }
    except ResolverDispatchError as exc:
        db.session.rollback()
        journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
        if journal is not None and journal.orchestration_status == 'running':
            record_execution_failure(
                journal,
                owner=owner,
                failure_class=FailureClass.TERMINAL,
                message=str(exc),
            )
            record_operational_failure(journal)
            db.session.commit()
        raise
    except ResolverOperationalError:
        db.session.rollback()
        raise
    except Exception as exc:
        db.session.rollback()
        journal = db.session.get(IntelligenceExecutionJournal, execution_journal_id)
        if journal is not None and journal.orchestration_status == 'running':
            retryable = record_execution_failure(
                journal,
                owner=owner,
                failure_class=FailureClass.RETRYABLE,
                message=str(exc),
            )
            record_operational_failure(journal)
            db.session.commit()
            if retryable:
                raise self.retry(exc=exc)
        raise


@shared_task(
    name='app.resolver.tasks.reconcile_stale_execution_leases',
    acks_late=True,
    reject_on_worker_lost=True,
    queue='resolver-maintenance',
)
def reconcile_stale_execution_leases() -> dict[str, int]:
    """Recover resolver executions abandoned by stopped or lost workers."""
    return recover_stale_execution_leases()
