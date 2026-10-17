from __future__ import annotations

from celery import shared_task

from app.extensions.db import db
from app.models.job import JobExecution
from app.platform_operations.jobs.notifications import dispatch_failed_job_event
from app.platform_operations.jobs.scheduler import dispatch_due_job_policies
from app.platform_operations.jobs.service import recover_stale_jobs


@shared_task(
    name='app.platform_operations.jobs.tasks.dispatch_scheduled_jobs',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_scheduled_jobs() -> dict[str, object]:
    """Dispatch every due database-backed job policy through the job registry."""
    return dispatch_due_job_policies()


@shared_task(
    name='app.platform_operations.jobs.tasks.reconcile_stale_jobs',
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_stale_jobs() -> dict[str, int]:
    """Release canonical job slots abandoned by stopped or lost workers."""
    return recover_stale_jobs()


@shared_task(
    name='app.platform_operations.jobs.tasks.dispatch_failed_job_notification',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_failed_job_notification(job_id: int) -> dict[str, object]:
    """Read authoritative committed failure before sending through governed channels."""
    job = db.session.get(JobExecution, int(job_id))
    if job is None or job.status != 'failed':
        return {'status': 'skipped', 'reason': 'job_missing_or_not_failed', 'job_id': job_id}
    return {'status': 'completed', **dispatch_failed_job_event(job)}
