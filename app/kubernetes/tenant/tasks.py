from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.kubernetes.tenant.audit import record_tenant_sync_terminal_audit
from app.kubernetes.tenant.sync_service import build_tenant_inventory_snapshot
from app.models.job import JobExecution
from app.platform_operations.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.platform_operations.jobs.service import subscriber_user_ids
from app.platform_operations.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _job_for_execution(job_execution_id: int | None) -> JobExecution | None:
    if job_execution_id is None:
        return None
    return db.session.get(JobExecution, job_execution_id)


def _notification_copy(
    *,
    terminal_status: str,
    result: dict[str, Any],
) -> tuple[str, str, str, str]:
    tenant_count = int(result.get('tenant_count') or 0)
    namespace_count = int(result.get('namespace_count') or 0)
    covered_count = int(result.get('covered_namespace_count') or 0)
    cluster_count = int(result.get('tenant_cluster_count') or 0)
    exception_count = int(result.get('exception_count') or 0)
    cluster_word = 'cluster' if cluster_count == 1 else 'clusters'
    tenant_word = 'Tenant' if tenant_count == 1 else 'Tenants'
    namespace_word = 'namespace' if namespace_count == 1 else 'namespaces'

    if terminal_status == 'succeeded':
        return (
            'success',
            'Tenant Sync Completed',
            (
                f'{tenant_count} {tenant_word} and {namespace_count} {namespace_word} were correlated '
                f'across {cluster_count} Tenant {cluster_word}.'
            ),
            (
                f'Snapshot coverage is current: {covered_count} of {namespace_count} governed '
                'namespaces matched committed Kubernetes inventory.'
            ),
        )
    if terminal_status == 'partially_succeeded':
        return (
            'warning',
            'Tenant Sync Completed With Exceptions',
            (
                f'{tenant_count} {tenant_word} and {namespace_count} {namespace_word} were correlated '
                f'across {cluster_count} Tenant {cluster_word}.'
            ),
            (
                f'{exception_count} snapshot exception{"s" if exception_count != 1 else ""} require review. '
                f'{covered_count} of {namespace_count} governed namespaces matched committed Kubernetes inventory.'
            ),
        )
    if terminal_status == 'canceled':
        return (
            'warning',
            'Tenant Sync Canceled',
            'Tenant inventory synchronization was canceled before completion.',
            'Review Jobs & Executions for the final worker state.',
        )
    return (
        'error',
        'Tenant Sync Failed',
        'KAORI could not complete Tenant inventory synchronization.',
        'Review Jobs & Executions before retrying.',
    )


def _notify_requesters(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    result: dict[str, Any],
    terminal_status: str,
) -> set[int]:
    job = _job_for_execution(job_execution_id)
    user_ids: set[int] = set()
    if job is not None:
        user_ids.update(subscriber_user_ids(job))
    if fallback_user_id is not None:
        user_ids.add(int(fallback_user_id))
    if not user_ids:
        return set()

    status, title, message, detail = _notification_copy(
        terminal_status=terminal_status,
        result=result,
    )
    persisted: set[int] = set()
    for user_id in sorted(user_ids):
        try:
            create_notification(
                user_id=user_id,
                event_type='kubernetes_tenant_inventory_sync',
                status=status,
                title=title,
                message=message,
                detail=detail,
                action_url='/kubernetes/tenant/',
                metadata={
                    'job_execution_id': job.id if job is not None else None,
                    'job_public_id': job.public_id if job is not None else None,
                    'trigger_type': result.get('trigger_type'),
                    'tenant_count': result.get('tenant_count'),
                    'namespace_count': result.get('namespace_count'),
                    'covered_namespace_count': result.get('covered_namespace_count'),
                    'tenant_cluster_count': result.get('tenant_cluster_count'),
                    'exception_count': result.get('exception_count'),
                    'terminal_status': terminal_status,
                },
            )
            persisted.add(user_id)
        except Exception:
            db.session.rollback()
            logger.exception('Could not persist Tenant sync completion notification for user %s.', user_id)
    return persisted


def _finish_evidence(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    terminal_status: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    job = _job_for_execution(job_execution_id)
    enriched = dict(result)
    enriched['activity_audit_saved'] = record_tenant_sync_terminal_audit(
        job=job,
        fallback_user_id=fallback_user_id,
        terminal_status=terminal_status,
        result=enriched,
    )
    enriched['notification_deck_user_ids'] = sorted(
        _notify_requesters(
            job_execution_id=job_execution_id,
            fallback_user_id=fallback_user_id,
            result=enriched,
            terminal_status=terminal_status,
        )
    )
    return enriched


@shared_task(
    bind=True,
    name='app.kubernetes.tenant.tasks.sync_tenant_inventory',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_tenant_inventory_task(
    self,
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    """Materialize committed Tenant inventory correlation on the inventory worker."""

    context = JobExecutionContext(
        task_id=str(self.request.id),
        job_execution_id=job_execution_id,
    )
    context.start(message='Preparing Tenant inventory synchronization.', total=100)
    try:
        context.checkpoint(
            current=20,
            total=100,
            message='Reading committed Tenant ownership and Kubernetes inventory evidence.',
        )
        snapshot = build_tenant_inventory_snapshot()
        context.checkpoint(
            current=80,
            total=100,
            message='Finalizing Tenant inventory correlation snapshot.',
        )
        terminal_status = 'partially_succeeded' if snapshot['exception_count'] else 'succeeded'
        result = _finish_evidence(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status=terminal_status,
            result={
                **snapshot,
                'trigger_type': trigger_type,
                'requested_by_user_id': requested_by_user_id,
            },
        )
        context.succeed(
            result_summary=result,
            result_type='kubernetes_tenant_inventory_snapshot',
            partial=terminal_status == 'partially_succeeded',
        )
        return result
    except JobCancellationRequested:
        result = _finish_evidence(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='canceled',
            result={
                'trigger_type': trigger_type,
                'requested_by_user_id': requested_by_user_id,
                'tenant_count': 0,
                'namespace_count': 0,
                'covered_namespace_count': 0,
                'tenant_cluster_count': 0,
                'exception_count': 0,
            },
        )
        job = _job_for_execution(job_execution_id)
        if job is not None:
            job.result_summary_json = result
            db.session.commit()
        context.canceled(message='Tenant inventory synchronization was canceled by an operator.')
        raise
    except Exception as exc:
        db.session.rollback()
        result = _finish_evidence(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='failed',
            result={
                'trigger_type': trigger_type,
                'requested_by_user_id': requested_by_user_id,
                'tenant_count': 0,
                'namespace_count': 0,
                'covered_namespace_count': 0,
                'tenant_cluster_count': 0,
                'exception_count': 0,
            },
        )
        job = _job_for_execution(job_execution_id)
        if job is not None:
            job.result_summary_json = result
            db.session.commit()
        context.fail(exc, error_code='kubernetes_tenant_inventory_sync_failed')
        logger.exception('Tenant inventory synchronization failed unexpectedly.')
        raise
