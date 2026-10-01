from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.kubernetes.tenant.allocation_drift import (
    apply_managed_allocation_drift_observation,
    apply_provider_mirrored_policy_observation,
)
from app.kubernetes.tenant.audit import record_tenant_sync_terminal_audit
from app.kubernetes.tenant.capsule_allocation_governance import (
    apply_managed_capsule_shared_allocation_drift_observation,
)
from app.kubernetes.tenant.capsule_tenant_quota_governance import (
    apply_managed_capsule_tenant_quota_drift_observation,
)
from app.kubernetes.tenant.decommission_service import execute_tenant_decommission
from app.kubernetes.tenant.sync_service import (
    apply_missing_namespace_drift_from_inventory,
    build_tenant_inventory_snapshot,
)
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
    drifted_namespace_count = int(result.get('drifted_namespace_count') or 0)
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
                f'{drifted_namespace_count} namespace record{"s" if drifted_namespace_count != 1 else ""} '
                f'were newly marked Drifted; {covered_count} of {namespace_count} governed namespaces matched inventory.'
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
        missing_namespace_drift_ids = apply_missing_namespace_drift_from_inventory()
        allocation_drift = apply_managed_allocation_drift_observation()
        provider_policy_mirror = apply_provider_mirrored_policy_observation()
        capsule_shared_drift = apply_managed_capsule_shared_allocation_drift_observation()
        capsule_tenant_quota_drift = apply_managed_capsule_tenant_quota_drift_observation()

        allocation_drift_ids = list(allocation_drift['drifted_namespace_ids'])
        drifted_namespace_ids = sorted(set(missing_namespace_drift_ids + allocation_drift_ids))
        snapshot['drifted_namespace_count'] = len(drifted_namespace_ids)
        snapshot['drifted_namespace_ids'] = drifted_namespace_ids
        snapshot['missing_namespace_drift_count'] = len(missing_namespace_drift_ids)
        snapshot['allocation_drift_count'] = len(allocation_drift_ids)
        snapshot['allocation_observation_error_count'] = len(allocation_drift['observation_errors'])
        snapshot['provider_mirrored_policy_count'] = len(provider_policy_mirror['mirrored_namespace_ids'])
        snapshot['provider_mirrored_policy_updated_count'] = len(provider_policy_mirror['updated_namespace_ids'])
        snapshot['provider_mirrored_policy_error_count'] = len(provider_policy_mirror['observation_errors'])
        snapshot['capsule_shared_allocation_drift_count'] = len(capsule_shared_drift['drifted_intent_ids'])
        snapshot['capsule_shared_allocation_drift_ids'] = capsule_shared_drift['drifted_intent_ids']
        snapshot['capsule_shared_allocation_restored_ids'] = capsule_shared_drift['restored_intent_ids']
        snapshot['capsule_shared_allocation_observation_error_count'] = len(
            capsule_shared_drift['observation_errors']
        )
        snapshot['capsule_tenant_quota_drift_count'] = len(
            capsule_tenant_quota_drift['drifted_tenant_ids']
        )
        snapshot['capsule_tenant_quota_drift_ids'] = capsule_tenant_quota_drift['drifted_tenant_ids']
        snapshot['capsule_tenant_quota_observation_error_count'] = len(
            capsule_tenant_quota_drift['observation_errors']
        )

        allocation_exceptions = [
            {
                'cluster_id': item.get('cluster_id', ''),
                'namespace': item.get('namespace', ''),
                'reason': item.get('reason', 'Allocation drift requires review.'),
            }
            for item in allocation_drift['drifted_namespaces']
        ]
        observation_exceptions = [
            {
                'cluster_id': '',
                'namespace': item.get('namespace', ''),
                'reason': f'Allocation observation failed: {item.get("reason", "unknown error")}',
            }
            for item in allocation_drift['observation_errors']
        ]
        provider_policy_exceptions = [
            {
                'cluster_id': '',
                'namespace': item.get('namespace', ''),
                'reason': f'Provider policy mirror failed: {item.get("reason", "unknown error")}',
            }
            for item in provider_policy_mirror['observation_errors']
        ]
        capsule_shared_exceptions = [
            {
                'cluster_id': '',
                'namespace': f"Tenant/{item.get('tenant_id', '')}",
                'reason': (
                    'Capsule shared allocation observation failed: '
                    + str(item.get('reason') or 'unknown error')
                ),
            }
            for item in capsule_shared_drift['observation_errors']
        ]
        capsule_tenant_quota_exceptions = [
            {
                'cluster_id': '',
                'namespace': f"Tenant/{item.get('tenant_id', '')}",
                'reason': (
                    'Capsule Tenant quota observation failed: '
                    + str(item.get('reason') or 'unknown error')
                ),
            }
            for item in capsule_tenant_quota_drift['observation_errors']
        ]
        snapshot['exceptions'] = (
            list(snapshot.get('exceptions') or [])
            + allocation_exceptions
            + observation_exceptions
            + provider_policy_exceptions
            + capsule_shared_exceptions
            + capsule_tenant_quota_exceptions
        )[:25]
        snapshot['exception_count'] = (
            int(snapshot.get('exception_count') or 0)
            + len(allocation_exceptions)
            + len(observation_exceptions)
            + len(provider_policy_exceptions)
            + len(capsule_shared_exceptions)
            + len(capsule_tenant_quota_exceptions)
        )
        db.session.commit()
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


def _notify_decommission_requesters(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    result: dict[str, Any],
    terminal_status: str,
    error_message: str | None = None,
) -> set[int]:
    job = _job_for_execution(job_execution_id)
    user_ids: set[int] = set()
    if job is not None:
        user_ids.update(subscriber_user_ids(job))
    if fallback_user_id is not None:
        user_ids.add(int(fallback_user_id))

    tenant_name = str(result.get('tenant_name') or result.get('tenant_id') or 'Tenant')
    if terminal_status == 'succeeded':
        status = 'success'
        title = 'Tenant Decommission Completed'
        message = f'{tenant_name} finished governed teardown.'
        detail = 'Native Kubernetes provider absence was verified before the final lifecycle state was committed.'
    elif terminal_status == 'canceled':
        status = 'warning'
        title = 'Tenant Decommission Canceled'
        message = f'{tenant_name} remains frozen in Decommissioning state.'
        detail = 'Review committed teardown evidence before retrying the decommission job.'
    else:
        status = 'error'
        title = 'Tenant Decommission Requires Attention'
        message = f'{tenant_name} remains frozen because governed teardown did not complete.'
        detail = error_message or 'Review Jobs & Executions and the committed Tenant teardown evidence before retrying.'

    persisted: set[int] = set()
    for user_id in sorted(user_ids):
        try:
            create_notification(
                user_id=user_id,
                event_type='kubernetes_tenant_decommission',
                status=status,
                title=title,
                message=message,
                detail=detail,
                action_url='/kubernetes/tenant/tenants?section=registry',
                metadata={
                    'job_execution_id': job.id if job is not None else None,
                    'job_public_id': job.public_id if job is not None else None,
                    'tenant_id': result.get('tenant_id'),
                    'tenant_generation': result.get('tenant_generation'),
                    'provider_key': result.get('provider_key'),
                    'terminal_status': terminal_status,
                },
            )
            persisted.add(user_id)
        except Exception:
            db.session.rollback()
            logger.exception('Could not persist Tenant decommission notification for user %s.', user_id)
    return persisted


@shared_task(
    bind=True,
    name='app.kubernetes.tenant.tasks.decommission_tenant',
    acks_late=True,
    reject_on_worker_lost=True,
)
def decommission_tenant_task(
    self,
    *,
    tenant_id: str,
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    """Execute provider-aware Tenant teardown outside the web request."""

    context = JobExecutionContext(
        task_id=str(self.request.id),
        job_execution_id=job_execution_id,
    )
    context.start(message='Preparing governed Tenant decommission.', total=100)
    result: dict[str, Any] = {'tenant_id': tenant_id}
    try:
        result = execute_tenant_decommission(
            tenant_id=tenant_id,
            actor_user_id=requested_by_user_id,
            progress=lambda percent, message: context.checkpoint(
                current=percent,
                total=100,
                message=message,
            ),
        )
        result['notification_deck_user_ids'] = sorted(
            _notify_decommission_requesters(
                job_execution_id=job_execution_id,
                fallback_user_id=requested_by_user_id,
                result=result,
                terminal_status='succeeded',
            )
        )
        context.succeed(
            result_summary=result,
            result_type='kubernetes_tenant_decommission',
        )
        return result
    except JobCancellationRequested:
        result['notification_deck_user_ids'] = sorted(
            _notify_decommission_requesters(
                job_execution_id=job_execution_id,
                fallback_user_id=requested_by_user_id,
                result=result,
                terminal_status='canceled',
            )
        )
        job = _job_for_execution(job_execution_id)
        if job is not None:
            job.result_summary_json = result
            db.session.commit()
        context.canceled(message='Tenant decommission was canceled; the Tenant remains frozen.')
        raise
    except Exception as exc:
        db.session.rollback()
        result['error'] = str(exc)[:1000]
        result['notification_deck_user_ids'] = sorted(
            _notify_decommission_requesters(
                job_execution_id=job_execution_id,
                fallback_user_id=requested_by_user_id,
                result=result,
                terminal_status='failed',
                error_message=result['error'],
            )
        )
        job = _job_for_execution(job_execution_id)
        if job is not None:
            job.result_summary_json = result
            db.session.commit()
        context.fail(exc, error_code='kubernetes_tenant_decommission_failed')
        logger.exception('Tenant decommission failed and remains fail-closed.')
        raise
