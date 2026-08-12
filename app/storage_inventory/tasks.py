from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.integrations.registry import get_integration
from app.jobs.execution import JobExecutionContext
from app.models.minio import MinioInstance
from app.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_result(
    *,
    requested_by_user_id: int | None,
    total_count: int,
    synced_count: int,
    bucket_count: int,
    failed_systems: list[str],
    started_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    failed_count = len(failed_systems)
    if failed_count == total_count and total_count:
        status = 'error'
        title = 'Object Storage Inventory Sync Failed'
        message = f'All {total_count} eligible object-storage systems failed to synchronize.'
    elif failed_count:
        status = 'warning'
        title = 'Object Storage Inventory Sync Completed With Warnings'
        message = f'{synced_count} systems synchronized and {failed_count} failed.'
    else:
        status = 'success'
        title = 'Object Storage Inventory Sync Completed'
        message = f'All {synced_count} eligible object-storage systems synchronized successfully.'

    failed_preview = ', '.join(failed_systems[:3])
    if failed_count > 3:
        failed_preview = f'{failed_preview}, +{failed_count - 3} more'
    detail = (
        f'Failed systems: {failed_preview}. Existing committed snapshots remain available for failed targets.'
        if failed_systems
        else f'{bucket_count} bucket record(s) are represented by the latest committed object-storage snapshots.'
    )
    return {
        'status': status,
        'title': title,
        'message': message,
        'detail': detail,
        'total_count': total_count,
        'processed_count': total_count,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'bucket_count': bucket_count,
        'failed_systems': failed_systems,
        'requested_by_user_id': requested_by_user_id,
        'started_at': started_at,
        'finished_at': _now_iso(),
        'duration_seconds': duration_seconds,
        'current_system_name': None,
    }


@shared_task(
    bind=True,
    name='app.storage_inventory.tasks.sync_all_object_storage',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_all_object_storage_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]] | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)
    started_timer = perf_counter()
    started_at = _now_iso()
    targets = list(targets or [])
    total_count = len(targets)
    synced_count = 0
    bucket_count = 0
    failed_systems: list[str] = []
    failure_evidence: list[dict[str, str]] = []
    context.start(
        message='Synchronizing object-storage inventory for all eligible managed systems.',
        total=total_count,
    )

    try:
        for index, target in enumerate(targets, start=1):
            instance_id = int(target['instance_id'])
            system_name = target['system_name']
            context.checkpoint(
                current=index - 1,
                total=total_count,
                message=f'Synchronizing {system_name}.',
            )
            self.update_state(
                state='PROGRESS',
                meta={
                    'requested_by_user_id': requested_by_user_id,
                    'job_execution_id': job_execution_id,
                    'total_count': total_count,
                    'processed_count': index - 1,
                    'synced_count': synced_count,
                    'failed_count': len(failed_systems),
                    'current_system_name': system_name,
                    'heartbeat_at': _now_iso(),
                },
            )
            try:
                instance = db.session.get(MinioInstance, instance_id)
                if instance is None:
                    raise LookupError('The MinIO connection was deleted after the inventory job was admitted.')
                result = get_integration('minio').execute('inventory.sync', instance)
                synced_count += 1
                bucket_count += int(result.get('total') or 0)
            except Exception as exc:
                db.session.rollback()
                failed_systems.append(system_name)
                failure_evidence.append(
                    {
                        'instance_id': str(instance_id),
                        'system_name': system_name,
                        'error_type': type(exc).__name__,
                        'message': str(exc),
                    }
                )
                logger.exception('Object-storage inventory synchronization failed for %s.', system_name)

            context.checkpoint(
                current=index,
                total=total_count,
                message=(
                    f'Synchronized {system_name}.'
                    if system_name not in failed_systems
                    else f'Finished {system_name} with an error.'
                ),
            )

        result = _build_result(
            requested_by_user_id=requested_by_user_id,
            total_count=total_count,
            synced_count=synced_count,
            bucket_count=bucket_count,
            failed_systems=failed_systems,
            started_at=started_at,
            duration_seconds=round(perf_counter() - started_timer, 1),
        )
        result['failure_evidence'] = failure_evidence
        if requested_by_user_id is not None:
            create_notification(
                user_id=requested_by_user_id,
                event_type='object_storage_inventory_sync',
                status=result['status'],
                title=result['title'],
                message=result['message'],
                detail=result['detail'],
                action_url='/storage/object-storage/',
                metadata={
                    'task_id': task_id,
                    'job_execution_id': job_execution_id,
                    'total_count': total_count,
                    'synced_count': synced_count,
                    'failed_count': len(failed_systems),
                    'bucket_count': bucket_count,
                    'failed_systems': failed_systems,
                    'failure_evidence': failure_evidence,
                    'duration_seconds': result['duration_seconds'],
                },
            )
        context.succeed(
            result_summary=result,
            result_type='object_storage_inventory_sync',
            partial=bool(failed_systems),
        )
        return result
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='object_storage_inventory_sync_failed')
        logger.exception('Unexpected failure while synchronizing object-storage inventory.')
        return {
            'status': 'error',
            'title': 'Object Storage Inventory Sync Interrupted',
            'message': 'The background synchronization stopped before all systems were processed.',
            'detail': 'Review the inventory worker and MinIO provider evidence before retrying.',
            'total_count': total_count,
            'processed_count': synced_count + len(failed_systems),
            'synced_count': synced_count,
            'failed_count': len(failed_systems),
            'bucket_count': bucket_count,
            'failed_systems': failed_systems,
            'failure_evidence': failure_evidence,
            'requested_by_user_id': requested_by_user_id,
            'started_at': started_at,
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
            'current_system_name': None,
            'error_type': type(exc).__name__,
        }
