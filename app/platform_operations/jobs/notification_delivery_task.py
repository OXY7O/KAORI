from __future__ import annotations

from celery import shared_task

from app.extensions.db import db
from app.models.job import JobExecution
from app.platform_operations.jobs.notifications import dispatch_failed_job_event


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
