from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError

from app.artifact_registry.correlation import refresh_registry_workload_bindings
from app.platform_operations.jobs.execution import JobExecutionContext


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@shared_task(
    bind=True,
    name='app.artifact_registry.correlation_tasks.materialize_registry_runtime_correlation',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_registry_runtime_correlation_task(
    self,
    *,
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    started = perf_counter()
    context.start(
        message='Preparing committed Registry to Kubernetes runtime correlation.',
        total=0,
        percent=5,
        stage='Preparing Runtime Correlation',
        target='Registry and Kubernetes Inventory',
    )
    try:
        context.checkpoint(
            current=0,
            total=0,
            percent=20,
            stage='Indexing Runtime Correlation',
            target='Committed Registry Inventory',
            message='Indexing committed Registry artifact identity before runtime matching.',
        )
        last_reported_percent = -1

        def report_correlation_progress(current: int, total: int, target: str) -> None:
            nonlocal last_reported_percent
            fraction = current / max(total, 1) if total else 0
            overall_percent = 35 if current == 0 else min(35 + int(fraction * 55), 90)
            is_boundary = current in {0, total}
            if not is_boundary and overall_percent <= last_reported_percent:
                return
            last_reported_percent = overall_percent
            message = (
                f'Processed {current} of {total} committed Kubernetes Pods.'
                if total
                else 'No current committed Kubernetes Pods are available to correlate.'
            )
            context.checkpoint(
                current=current,
                total=total,
                percent=overall_percent,
                stage='Materializing Runtime Correlation',
                target=target,
                message=message,
            )
            self.update_state(
                state='PROGRESS',
                meta={
                    'requested_by_user_id': requested_by_user_id,
                    'job_execution_id': job_execution_id,
                    'processed_count': current,
                    'total_count': total,
                    'progress_percent': overall_percent,
                    'progress_stage': 'Materializing Runtime Correlation',
                    'current_target': target,
                    'message': message,
                    'heartbeat_at': _now_iso(),
                },
            )

        result = refresh_registry_workload_bindings(
            progress_callback=report_correlation_progress,
        )
    except (RuntimeError, ValueError, SQLAlchemyError) as exc:
        context.fail(
            exc,
            error_code='artifact_registry_runtime_correlation_failed',
        )
        raise

    result = {
        **result,
        'requested_by_user_id': requested_by_user_id,
        'finished_at': _now_iso(),
        'duration_seconds': round(perf_counter() - started, 1),
    }
    context.checkpoint(
        current=int(result.get('pods_evaluated') or 0),
        total=int(result.get('pods_evaluated') or 0),
        percent=98,
        stage='Finalizing Runtime Correlation',
        target='Committed Runtime Bindings',
        message='Finalizing committed Registry runtime blast-radius evidence.',
    )
    context.succeed(
        result_summary=result,
        result_type='artifact_registry_runtime_correlation',
        partial=False,
    )
    return result
