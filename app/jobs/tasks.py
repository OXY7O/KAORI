from __future__ import annotations

from celery import shared_task

from app.jobs.scheduler import dispatch_due_job_policies
from app.jobs.service import recover_stale_jobs


@shared_task(
    name='app.jobs.tasks.dispatch_scheduled_jobs',
    acks_late=True,
    reject_on_worker_lost=True,
)
def dispatch_scheduled_jobs() -> dict[str, object]:
    """Dispatch every due database-backed job policy through the job registry."""
    return dispatch_due_job_policies()


@shared_task(
    name='app.jobs.tasks.reconcile_stale_jobs',
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_stale_jobs() -> dict[str, int]:
    """Release canonical job slots abandoned by stopped or lost workers."""
    return recover_stale_jobs()
