from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.governance.tls_certificates.results import classify_tls_sync_outcome
from app.governance.tls_certificates.service import sync_tls_certificates_for_cluster
from app.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.jobs.service import subscriber_user_ids
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _notify_requesters(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    result: dict[str, Any],
) -> None:
    user_ids: set[int] = set()
    if job_execution_id is not None:
        job = db.session.get(JobExecution, job_execution_id)
        if job is not None:
            user_ids.update(subscriber_user_ids(job))
    if fallback_user_id is not None:
        user_ids.add(int(fallback_user_id))
    if not user_ids:
        return

    failed_count = int(result['failed_cluster_count'])
    status = (
        'error'
        if failed_count and not int(result['successful_cluster_count'])
        else 'warning'
        if failed_count
        else 'success'
    )
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
                    f'{result["collected_count"]} TLS Secrets were collected across '
                    f'{result["successful_cluster_count"]} clusters.'
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

        result: dict[str, Any] = {
            'trigger_type': trigger_type,
            'target_count': total_targets,
            'successful_cluster_count': successful_clusters,
            'failed_cluster_count': len(failures),
            'collected_count': collected_count,
            'failures': failures,
            'started_at': started_at,
            'completed_at': _now_iso(),
        }
        terminal_status = classify_tls_sync_outcome(
            target_count=total_targets,
            failed_count=len(failures),
        )
        if terminal_status == 'failed':
            if job_execution_id is not None:
                failed_job = db.session.get(JobExecution, job_execution_id)
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
        _notify_requesters(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            result=result,
        )
        return result
    except JobCancellationRequested:
        context.canceled(message='TLS certificate synchronization was canceled by an operator.')
        raise
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='tls_certificate_sync_failed')
        logger.exception('TLS certificate inventory synchronization failed unexpectedly.')
        raise
