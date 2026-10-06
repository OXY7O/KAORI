from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.artifact_registry.sync import sync_registry_inventory
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.platform_operations.jobs.execution import JobExecutionContext
from app.platform_operations.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _inventory_sync_result(
    *,
    total: int,
    synced: int,
    artifact_count: int,
    failures: list[dict[str, str]],
    requested_by_user_id: int | None,
    started: float,
) -> dict[str, Any]:
    status = 'error' if failures and not synced else ('warning' if failures else 'success')
    return {
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
            progress_meta = {
                'requested_by_user_id': requested_by_user_id,
                'job_execution_id': job_execution_id,
                'total_count': total,
                'processed_count': index - 1,
                'synced_count': synced,
                'failed_count': len(failures),
                'current_instance_name': instance_name,
                'heartbeat_at': _now_iso(),
            }
            last_reported_percent = -1

            def report_inventory_progress(item_current: int, item_total: int, item_name: str) -> None:
                nonlocal last_reported_percent
                local_fraction = item_current / max(item_total, 1) if item_total else 0
                completed_fraction = (index - 1) + local_fraction
                overall_percent = min(5 + int((completed_fraction / max(total, 1)) * 88), 93)
                is_boundary = item_current in {0, item_total}
                if not is_boundary and overall_percent <= last_reported_percent:
                    return
                last_reported_percent = overall_percent
                stage = 'Discovering Registry Inventory' if item_total == 0 else 'Collecting Registry Inventory'
                target_label = f'{instance_name} · {item_name}' if item_name else instance_name
                message = (
                    f'Collected {item_current} of {item_total} repositories for {instance_name}.'
                    if item_total
                    else f'Discovering Registry inventory for {instance_name}.'
                )
                context.checkpoint(
                    current=index - 1,
                    total=total,
                    percent=overall_percent,
                    stage=stage,
                    target=target_label,
                    message=message,
                )
                progress_meta.update(
                    {
                        'progress_percent': overall_percent,
                        'progress_stage': stage,
                        'message': message,
                        'current_item_name': item_name,
                        'item_processed_count': item_current,
                        'item_total_count': item_total,
                        'heartbeat_at': _now_iso(),
                    }
                )
                self.update_state(state='PROGRESS', meta=progress_meta)

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
                    raise LookupError('The Registry integration was deleted after the inventory job was admitted.')
                result = sync_registry_inventory(
                    identity,
                    progress_callback=report_inventory_progress,
                )
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

        result = _inventory_sync_result(
            total=total,
            synced=synced,
            artifact_count=artifact_count,
            failures=failures,
            requested_by_user_id=requested_by_user_id,
            started=started,
        )
        status = str(result['status'])
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
        if failures and not synced:
            context.fail(
                'All eligible Registry providers failed inventory synchronization.',
                error_code='artifact_registry_inventory_sync_failed',
            )
        else:
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
