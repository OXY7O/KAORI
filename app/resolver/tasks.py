from __future__ import annotations

from celery import shared_task

from app.resolver.orchestration import recover_stale_execution_leases


@shared_task(
    name='app.resolver.tasks.reconcile_stale_execution_leases',
    acks_late=True,
    reject_on_worker_lost=True,
    queue='resolver-maintenance',
)
def reconcile_stale_execution_leases() -> dict[str, int]:
    """Recover resolver executions abandoned by stopped or lost workers."""
    return recover_stale_execution_leases()
