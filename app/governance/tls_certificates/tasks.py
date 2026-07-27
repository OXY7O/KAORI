from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.governance.tls_certificates.results import classify_tls_sync_outcome
from app.governance.tls_certificates.service import sync_tls_certificates_for_cluster
from app.jobs.audit import is_automatic_execution
from app.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.jobs.service import subscriber_user_ids
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _job_for_execution(job_execution_id: int | None) -> JobExecution | None:
    if job_execution_id is None:
        return None
    return db.session.get(JobExecution, job_execution_id)


def _with_job_metadata(
    result: dict[str, Any],
    *,
    job_execution_id: int | None,
) -> dict[str, Any]:
    enriched = dict(result)
    job = _job_for_execution(job_execution_id)
    if job is not None:
        enriched['job_execution_id'] = job.id
        enriched['job_public_id'] = job.public_id
        enriched['celery_task_id'] = job.celery_task_id
    return enriched


def _record_terminal_audit(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    terminal_status: str,
    result: dict[str, Any],
) -> None:
    job = _job_for_execution(job_execution_id)
    if job is None or is_automatic_execution(job):
        return

    action = f'governance_tls_secret_sync_{terminal_status}'
    existing = AuditEvent.query.filter_by(
        target_type='job_execution',
        target_id=job.public_id,
        action=action,
    ).first()
    if existing is not None:
        return

    summary_by_status = {
        'succeeded': 'TLS Secret synchronization completed successfully.',
        'partially_succeeded': 'TLS Secret synchronization completed with warnings.',
        'failed': 'TLS Secret synchronization failed.',
        'canceled': 'TLS Secret synchronization was canceled.',
    }
    event = AuditEvent()
    event.actor_user_id = job.requested_by_user_id or fallback_user_id
    event.target_type = 'job_execution'
    event.target_id = job.public_id
    event.action = action
    event.summary = summary_by_status.get(
        terminal_status,
        f'TLS Secret synchronization finished with status {terminal_status}.',
    )[:255]
    event.metadata_json = {
        'job_execution_id': job.id,
        'job_public_id': job.public_id,
        'job_type': job.job_type,
        'operation': job.operation,
        'queue_name': job.queue_name,
        'status': terminal_status,
        'result_summary': result,
    }
    try:
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Could not persist terminal TLS sync audit event for job %s.', job.public_id)


def _notify_requesters(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    result: dict[str, Any],
) -> None:
    user_ids: set[int] = set()
    job = _job_for_execution(job_execution_id)
    if job is not None:
        user_ids.update(subscriber_user_ids(job))
    if fallback_user_id is not None:
        user_ids.add(int(fallback_user_id))
    if not user_ids:
        return

    failed_count = int(result.get('failed_cluster_count') or 0)
    successful_count = int(result.get('successful_cluster_count') or 0)
    collected_count = int(result.get('collected_count') or 0)
    status = 'error' if failed_count and not successful_count else 'warning' if failed_count else 'success'
    for user_id in sorted(user_ids):
        try:
            create_notification(
                user_id=user_id,
                event_type='governance_tls_secret_sync',
                status=status,
                title=(
                    'TLS Secret Sync Failed'
                    if status == 'error'
                    else 'TLS Secret Sync Completed With Warnings'
                    if failed_count
                    else 'TLS Secret Sync Completed'
                ),
                message=(
                    f'{collected_count} TLS Secrets were collected across '
                    f'{successful_count} clusters.'
                ),
                detail=(
                    f'{failed_count} cluster syncs require review in Jobs & Executions.'
                    if failed_count
                    else 'Certificate expiry, SAN coverage, and Ingress usage are now current.'
                ),
                action_url='/governance/tls-certificates',
                metadata=result,
            )
        except Exception:
            db.session.rollback()
            logger.exception('Could not persist TLS sync completion notification for user %s.', user_id)


@shared_task(
    bind=True,
    name='app.governance.tls_certificates.tasks.sync_tls_certificates',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_tls_certificates_task(
    self,
    *,
    targets: list[dict[str, str]],
    requested_by_user_id: int | None,
    trigger_type: str,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id=task_id, job_execution_id=job_execution_id)
    total_targets = len(targets)
    context.start(message='Preparing TLS certificate inventory synchronization.', total=total_targets)

    collected_count = 0
    successful_clusters = 0
    failures: list[dict[str, str]] = []
    started_at = _now_iso()

    try:
        for index, target in enumerate(targets, start=1):
            cluster_id = str(target['cluster_id'])
            cluster_name = str(target.get('cluster_name') or cluster_id)
            context.checkpoint(
                current=index - 1,
                total=total_targets,
                message=f'Collecting TLS Secrets from {cluster_name}.',
            )
            cluster = db.session.get(Cluster, cluster_id)
            if cluster is None:
                failures.append(
                    {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'error': 'The cluster record no longer exists.',
                    }
                )
                context.checkpoint(
                    current=index,
                    total=total_targets,
                    message=f'Processed {index} of {total_targets} clusters.',
                )
                continue

            count, error = sync_tls_certificates_for_cluster(cluster)
            if error:
                failures.append(
                    {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'error': error,
                    }
                )
            else:
                successful_clusters += 1
                collected_count += count

            context.checkpoint(
                current=index,
                total=total_targets,
                message=f'Processed {index} of {total_targets} clusters.',
            )

        result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': len(failures),
                'collected_count': collected_count,
                'failures': failures,
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        terminal_status = classify_tls_sync_outcome(
            target_count=total_targets,
            failed_count=len(failures),
        )
        if terminal_status == 'failed':
            if job_execution_id is not None:
                failed_job = _job_for_execution(job_execution_id)
                if failed_job is not None:
                    failed_job.result_summary_json = result
                    db.session.commit()
            context.fail(
                'TLS certificate inventory synchronization failed for every target cluster.',
                error_code='tls_certificate_sync_failed',
            )
        else:
            context.succeed(
                result_summary=result,
                result_type='tls_certificate_inventory_sync',
                partial=terminal_status == 'partially_succeeded',
            )
        _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status=terminal_status,
            result=result,
        )
        _notify_requesters(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            result=result,
        )
        return result
    except JobCancellationRequested:
        context.canceled(message='TLS certificate synchronization was canceled by an operator.')
        canceled_result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': len(failures),
                'collected_count': collected_count,
                'failures': failures,
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='canceled',
            result=canceled_result,
        )
        raise
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='tls_certificate_sync_failed')
        failure_result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': max(total_targets - successful_clusters, 1),
                'collected_count': collected_count,
                'failures': [*failures, {'error': str(exc)}],
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='failed',
            result=failure_result,
        )
        _notify_requesters(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            result=failure_result,
        )
        logger.exception('TLS certificate inventory synchronization failed unexpectedly.')
        raise
