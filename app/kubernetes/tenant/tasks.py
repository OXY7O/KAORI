from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.kubernetes.tenant.sync_service import build_tenant_inventory_snapshot
from app.platform_operations.jobs.execution import JobCancellationRequested, JobExecutionContext

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='app.kubernetes.tenant.tasks.sync_tenant_inventory',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_tenant_inventory_task(
    self,
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    """Materialize committed Tenant inventory correlation on the inventory worker."""

    context = JobExecutionContext(
        task_id=str(self.request.id),
        job_execution_id=job_execution_id,
    )
    context.start(message='Preparing Tenant inventory synchronization.', total=100)
    try:
        context.checkpoint(
            current=20,
            total=100,
            message='Reading committed Tenant ownership and Kubernetes inventory evidence.',
        )
        snapshot = build_tenant_inventory_snapshot()
        context.checkpoint(
            current=80,
            total=100,
            message='Finalizing Tenant inventory correlation snapshot.',
        )
        result = {
            **snapshot,
            'trigger_type': trigger_type,
            'requested_by_user_id': requested_by_user_id,
        }
        context.succeed(
            result_summary=result,
            result_type='kubernetes_tenant_inventory_snapshot',
            partial=bool(snapshot['exception_count']),
        )
        return result
    except JobCancellationRequested:
        context.canceled(message='Tenant inventory synchronization was canceled by an operator.')
        raise
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='kubernetes_tenant_inventory_sync_failed')
        logger.exception('Tenant inventory synchronization failed unexpectedly.')
        raise
