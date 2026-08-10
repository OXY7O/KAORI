from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError

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
) -> bool:
    job = _job_for_execution(job_execution_id)
    if job is None or is_automatic_execution(job):
        return False

    action = f'governance_tls_secret_sync_{terminal_status}'
    existing = AuditEvent.query.filter_by(
        target_type='job_execution',
        target_id=job.public_id,
        action=action,
    ).first()
    if existing is not None:
        return True

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
        return True
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception('Could not persist terminal TLS sync audit event for job %s.', job.public_id)
        return False


def _notify_requesters(
    *,
    job_execution_id: int | None,
    fallback_user_id: int | None,
    result: dict[str, Any],
    terminal_status: str,
) -> set[int]:
    user_ids: set[int] = set()
    job = _job_for_execution(job_execution_id)
    if job is not None:
        user_ids.update(subscriber_user_ids(job))
    if fallback_user_id is not None:
        user_ids.add(int(fallback_user_id))
    if not user_ids:
        return set()

    persisted_user_ids: set[int] = set()
    failed_count = int(result.get('failed_cluster_count') or 0)
    successful_count = int(result.get('successful_cluster_count') or 0)
    collected_count = int(result.get('collected_count') or 0)
    warning_count = int(result.get('warning_cluster_count') or 0)
    status_by_terminal = {
        'succeeded': 'success',
        'partially_succeeded': 'warning',
        'canceled': 'warning',
        'failed': 'error',
    }
    status = status_by_terminal.get(terminal_status, 'info')
    title_by_terminal = {
        'succeeded': 'TLS Secret Sync Completed',
        'partially_succeeded': 'TLS Secret Sync Completed With Warnings',
        'canceled': 'TLS Secret Sync Canceled',
        'failed': 'TLS Secret Sync Failed',
    }
    for user_id in sorted(user_ids):
        try:
            create_notification(
                user_id=user_id,
                event_type='governance_tls_secret_sync',
                status=status,
                title=title_by_terminal.get(terminal_status, 'TLS Secret Sync Finished'),
                message=(
                    'TLS Secret synchronization was canceled before completion.'
                    if terminal_status == 'canceled'
                    else f'{collected_count} TLS Secrets were collected across {successful_count} clusters.'
                ),
                detail=(
                    'Review Jobs & Executions for the final cancellation state.'
                    if terminal_status == 'canceled'
                    else (
                        f'{failed_count} cluster syncs failed and {warning_count} completed with '
                        'incomplete Ingress mapping evidence.'
                    )
                    if failed_count and warning_count
                    else f'{failed_count} cluster syncs require review in Jobs & Executions.'
                    if failed_count
                    else (
                        f'{warning_count} cluster syncs completed with incomplete Ingress mapping '
                        'evidence. Review collection evidence before relying on host coverage.'
                    )
                    if warning_count
                    else 'Certificate expiry, SAN coverage, and Ingress usage are now current.'
                ),
                action_url='/governance/tls-certificates',
                metadata={
                    'job_execution_id': result.get('job_execution_id'),
                    'job_public_id': result.get('job_public_id'),
                    'trigger_type': result.get('trigger_type'),
                    'target_count': result.get('target_count'),
                    'successful_cluster_count': successful_count,
                    'failed_cluster_count': failed_count,
                    'warning_cluster_count': warning_count,
                    'collected_count': collected_count,
                    'terminal_status': terminal_status,
                },
            )
            persisted_user_ids.add(user_id)
        except Exception:
            db.session.rollback()
            logger.exception('Could not persist TLS sync completion notification for user %s.', user_id)

    return persisted_user_ids


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
    progress_total = 100
    context.start(message='Preparing TLS certificate inventory synchronization.', total=progress_total)
    context.checkpoint(
        current=3,
        total=progress_total,
        message='Preparing TLS certificate inventory synchronization.',
    )

    collected_count = 0
    successful_clusters = 0
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    started_at = _now_iso()

    try:
        for index, target in enumerate(targets, start=1):
            cluster_id = str(target['cluster_id'])
            cluster_name = str(target.get('cluster_name') or cluster_id)
            last_reported_percent = -1

            def report_cluster_progress(local_percent: int, message: str) -> None:
                nonlocal last_reported_percent
                # Reserve 3% for preparation and 4% for finalization. The
                # remaining 93% is distributed evenly across target clusters.
                normalized_local = max(0, min(int(local_percent), 100))
                completed_fraction = (index - 1) + (normalized_local / 100)
                overall_percent = min(
                    3 + int((completed_fraction / max(total_targets, 1)) * 93),
                    96,
                )
                # Collector callbacks can run once per Secret. Persist only
                # meaningful percentage changes to avoid a database commit for
                # every individual record while retaining responsive progress.
                is_boundary = normalized_local in {0, 100}
                if not is_boundary and overall_percent < last_reported_percent + 2:
                    return
                last_reported_percent = max(last_reported_percent, overall_percent)
                context.checkpoint(
                    current=overall_percent,
                    total=progress_total,
                    message=message,
                )

            report_cluster_progress(0, f'Preparing TLS collection for {cluster_name}.')
            cluster = db.session.get(Cluster, cluster_id)
            if cluster is None:
                failures.append(
                    {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'error': 'The cluster record no longer exists.',
                    }
                )
                report_cluster_progress(100, f'Skipped unavailable cluster {cluster_name}.')
                continue

            cluster_result = sync_tls_certificates_for_cluster(
                cluster,
                progress_callback=report_cluster_progress,
            )
            if cluster_result.fatal_error:
                failures.append(
                    {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'error': cluster_result.fatal_error,
                    }
                )
            else:
                successful_clusters += 1
                collected_count += cluster_result.collected_count
                if cluster_result.warning:
                    warnings.append(
                        {
                            'cluster_id': cluster_id,
                            'cluster_name': cluster_name,
                            'warning': cluster_result.warning,
                        }
                    )

            report_cluster_progress(100, f'Processed {index} of {total_targets} clusters.')

        context.checkpoint(
            current=98,
            total=progress_total,
            message='Finalizing TLS Secret inventory synchronization.',
        )

        result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': len(failures),
                'collected_count': collected_count,
                'failures': failures,
                'warning_cluster_count': len(warnings),
                'warnings': warnings,
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        terminal_status = classify_tls_sync_outcome(
            target_count=total_targets,
            failed_count=len(failures),
            warning_count=len(warnings),
        )
        audit_saved = _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status=terminal_status,
            result=result,
        )
        deck_user_ids = _notify_requesters(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            result=result,
            terminal_status=terminal_status,
        )
        result['activity_audit_saved'] = audit_saved
        result['notification_deck_user_ids'] = sorted(deck_user_ids)

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
        return result
    except JobCancellationRequested:
        canceled_result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': len(failures),
                'collected_count': collected_count,
                'failures': failures,
                'warning_cluster_count': len(warnings),
                'warnings': warnings,
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        canceled_result['activity_audit_saved'] = _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='canceled',
            result=canceled_result,
        )
        canceled_result['notification_deck_user_ids'] = sorted(
            _notify_requesters(
                job_execution_id=job_execution_id,
                fallback_user_id=requested_by_user_id,
                result=canceled_result,
                terminal_status='canceled',
            )
        )
        canceled_job = _job_for_execution(job_execution_id)
        if canceled_job is not None:
            canceled_job.result_summary_json = canceled_result
            db.session.commit()
        context.canceled(message='TLS certificate synchronization was canceled by an operator.')
        raise
    except Exception as exc:
        db.session.rollback()
        failure_result = _with_job_metadata(
            {
                'trigger_type': trigger_type,
                'target_count': total_targets,
                'successful_cluster_count': successful_clusters,
                'failed_cluster_count': max(total_targets - successful_clusters, 1),
                'collected_count': collected_count,
                'failures': [*failures, {'error': 'Unexpected TLS certificate synchronization failure.'}],
                'warning_cluster_count': len(warnings),
                'warnings': warnings,
                'started_at': started_at,
                'completed_at': _now_iso(),
            },
            job_execution_id=job_execution_id,
        )
        failure_result['activity_audit_saved'] = _record_terminal_audit(
            job_execution_id=job_execution_id,
            fallback_user_id=requested_by_user_id,
            terminal_status='failed',
            result=failure_result,
        )
        failure_result['notification_deck_user_ids'] = sorted(
            _notify_requesters(
                job_execution_id=job_execution_id,
                fallback_user_id=requested_by_user_id,
                result=failure_result,
                terminal_status='failed',
            )
        )
        failed_job = _job_for_execution(job_execution_id)
        if failed_job is not None:
            failed_job.result_summary_json = failure_result
            db.session.commit()
        context.fail(exc, error_code='tls_certificate_sync_failed')
        logger.exception('TLS certificate inventory synchronization failed unexpectedly.')
        raise
