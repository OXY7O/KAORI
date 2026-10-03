from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.artifact_registry.governance import sync_registry_governance
from app.artifact_registry.sync import sync_registry_inventory
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.platform_operations.jobs.execution import JobExecutionContext
from app.platform_operations.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@shared_task(
    bind=True,
    name='app.artifact_registry.tasks.sync_all_registry',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_all_registry_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]] | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)
    started = perf_counter()
    targets = list(targets or [])
    total = len(targets)
    synced = 0
    artifact_count = 0
    failures: list[dict[str, str]] = []
    context.start(
        message='Preparing Artifact Registry inventory synchronization.',
        total=total,
        percent=1,
        stage='Preparing Inventory',
        target='Registry Estate',
    )
    try:
        for index, target in enumerate(targets, start=1):
            instance_name = target['instance_name']
            canonical_id = int(target['integration_instance_id'])
            context.checkpoint(
                current=index - 1,
                total=total,
                percent=max(2, min(5 + int(((index - 1) / max(total, 1)) * 90), 95)),
                stage='Collecting Registry Snapshot',
                target=instance_name,
                message=f'Collecting committed Registry evidence from {instance_name}.',
            )
            try:
                identity = db.session.get(IntegrationInstance, canonical_id)
                if identity is None:
                    raise LookupError(
                        'The Registry integration was deleted after the inventory job was admitted.'
                    )
                result = sync_registry_inventory(identity)
                try:
                    governance_result = sync_registry_governance(identity)
                except Exception as governance_exc:
                    db.session.rollback()
                    governance_result = {
                        'status': 'failed',
                        'error_type': type(governance_exc).__name__,
                        'message': str(governance_exc)[:1000],
                    }
                    logger.exception('Registry governance collection failed for %s.', instance_name)
                result['governance'] = governance_result
                synced += 1
                artifact_count += int(result.get('artifacts') or 0)
            except Exception as exc:
                db.session.rollback()
                failures.append(
                    {
                        'integration_instance_id': str(canonical_id),
                        'instance_name': instance_name,
                        'provider_key': str(target.get('provider_key') or ''),
                        'error_type': type(exc).__name__,
                        'message': str(exc),
                    }
                )
                logger.exception('Artifact Registry synchronization failed for %s.', instance_name)
            context.checkpoint(
                current=index,
                total=total,
                percent=min(5 + int((index / max(total, 1)) * 90), 95),
                stage='Registry Snapshot Completed',
                target=instance_name,
                message=f'Finished Registry collection for {instance_name}.',
            )

        status = 'error' if failures and not synced else ('warning' if failures else 'success')
        result = {
            'status': status,
            'title': (
                'Artifact Registry Inventory Sync Completed'
                if status != 'error'
                else 'Artifact Registry Inventory Sync Failed'
            ),
            'message': f'{synced} Registry provider(s) synchronized; {len(failures)} failed.',
            'detail': (
                'Failed providers retained their previous committed snapshots.'
                if failures
                else f'{artifact_count} artifact record(s) are represented by the latest committed snapshots.'
            ),
            'total_count': total,
            'synced_count': synced,
            'failed_count': len(failures),
            'artifact_count': artifact_count,
            'failure_evidence': failures,
            'requested_by_user_id': requested_by_user_id,
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started, 1),
        }
        if requested_by_user_id is not None:
            create_notification(
                user_id=requested_by_user_id,
                event_type='artifact_registry_inventory_sync',
                status=status,
                title=result['title'],
                message=result['message'],
                detail=result['detail'],
                action_url='/artifact-registry/',
                metadata={'task_id': task_id, 'job_execution_id': job_execution_id, **result},
            )
        context.succeed(
            result_summary=result,
            result_type='artifact_registry_inventory_sync',
            partial=bool(failures),
        )
        return result
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='artifact_registry_inventory_sync_failed')
        logger.exception('Unexpected Artifact Registry inventory synchronization failure.')
        raise
