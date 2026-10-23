from __future__ import annotations

from celery import shared_task

from app.intelligence.alert_signals.service import refresh_all_kubernetes_runtime_signals
from app.intelligence.alert_signals.vault_jobs import run_vault_alert_observation_job


@shared_task(
    name='app.intelligence.alert_signals.tasks.refresh_alert_signals',
    acks_late=True,
    reject_on_worker_lost=True,
)
def refresh_alert_signals() -> dict[str, object]:
    """Refresh compact operational signals used by fast Alert Intelligence rules."""

    return {'kubernetes_runtime_health': refresh_all_kubernetes_runtime_signals()}


@shared_task(
    bind=True,
    name='app.intelligence.alert_signals.tasks.observe_vault_alert_source',
    acks_late=True,
    reject_on_worker_lost=True,
)
def observe_vault_alert_source(
    self,
    *,
    binding_ids: list[int],
    job_execution_id: int | None = None,
) -> dict[str, int | str]:
    """Run only a canonical, explicitly requested manual JobExecution."""
    return run_vault_alert_observation_job(
        task_id=str(self.request.id or ''),
        job_execution_id=job_execution_id,
        binding_ids=binding_ids,
    )
