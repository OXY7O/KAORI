from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from app.artifact_registry.analytics import materialize_registry_analytics
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.platform_operations.jobs.execution import JobExecutionContext

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='app.artifact_registry.analytics_tasks.materialize_registry_analytics',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_registry_analytics_task(
    self,
    *,
    integration_instance_ids: list[int],
    requested_by_user_id: int | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    del requested_by_user_id
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    ids = [int(value) for value in integration_instance_ids]
    context.start(
        message='Preparing Artifact Registry analytics materialization.',
        total=len(ids),
        percent=1,
        stage='Preparing Analytics',
        target='Artifact Registry',
    )
    completed = 0
    failures: list[dict[str, str]] = []
    snapshot_ids: list[int] = []
    for index, identity_id in enumerate(ids, start=1):
        identity = db.session.get(IntegrationInstance, identity_id)
        if identity is None or identity.integration_type != 'registry':
            failures.append({'integration_instance_id': str(identity_id), 'message': 'Registry instance not found.'})
            continue
        context.checkpoint(
            current=index - 1,
            total=len(ids),
            percent=max(2, min(5 + int(((index - 1) / max(len(ids), 1)) * 90), 95)),
            stage='Materializing Registry Analytics',
            target=identity.name,
            message=f'Building committed analytics for {identity.name}.',
        )
        try:
            snapshot = materialize_registry_analytics(
                identity,
                job_execution_id=job_execution_id,
            )
        except Exception as exc:
            db.session.rollback()
            failures.append(
                {
                    'integration_instance_id': str(identity.id),
                    'instance_name': identity.name,
                    'error_type': type(exc).__name__,
                    'message': str(exc)[:1000],
                }
            )
            logger.exception('Registry analytics materialization failed for %s.', identity.name)
        else:
            completed += 1
            snapshot_ids.append(snapshot.id)

    result = {
        'status': 'error' if failures and not completed else ('warning' if failures else 'success'),
        'total_count': len(ids),
        'completed_count': completed,
        'failed_count': len(failures),
        'failure_evidence': failures,
        'snapshot_ids': snapshot_ids,
        'finished_at': datetime.now(UTC).isoformat(),
    }
    context.succeed(
        result_summary=result,
        result_type='artifact_registry_analytics_materialization',
        partial=bool(failures),
    )
    return result
