from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.artifact_registry.correlation.materialize import materialize_registry_runtime_correlation
from app.platform_operations.jobs.execution import JobExecutionContext


@shared_task(
    bind=True,
    name='app.artifact_registry.correlation.tasks.materialize_artifact_registry_runtime_correlation',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_artifact_registry_runtime_correlation_task(
    self,
    *,
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    started = perf_counter()
    context.start(
        message='Preparing committed Registry to Kubernetes runtime correlation.',
        total=1,
        percent=5,
        stage='Preparing Runtime Correlation',
        target='Registry and Kubernetes Inventory',
    )
    try:
        context.checkpoint(
            current=0,
            total=1,
            percent=35,
            stage='Materializing Runtime Correlation',
            target='Committed Inventory',
            message='Matching committed Kubernetes runtime image evidence to committed Registry artifacts.',
        )
        result = materialize_registry_runtime_correlation()
    except Exception as exc:
        context.fail(
            str(exc),
            error_code='artifact_registry_runtime_correlation_failed',
        )
        raise

    result = {
        **result,
        'requested_by_user_id': requested_by_user_id,
        'finished_at': datetime.now(UTC).isoformat(),
        'duration_seconds': round(perf_counter() - started, 1),
    }
    context.checkpoint(
        current=1,
        total=1,
        percent=98,
        stage='Finalizing Runtime Correlation',
        target='Committed Inventory',
        message='Finalizing committed Registry runtime blast-radius evidence.',
    )
    context.succeed(
        result_summary=result,
        result_type='artifact_registry_runtime_correlation',
        partial=False,
    )
    return result
