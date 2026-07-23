from __future__ import annotations

from celery import shared_task

from app.integrations.runtime.dispatcher import dispatch_integration_runtime_refresh


@shared_task(
    bind=True,
    name='app.integrations.runtime.tasks.refresh_integration_runtime',
    acks_late=True,
    reject_on_worker_lost=True,
)
def refresh_integration_runtime(self) -> dict[str, object]:
    """Celery entrypoint for the canonical integration runtime dispatcher."""
    return dispatch_integration_runtime_refresh()
