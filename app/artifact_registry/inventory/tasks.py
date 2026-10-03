from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.artifact_registry.inventory.sync import sync_registry_instance
from app.models.integration import IntegrationInstance
from app.platform_operations.jobs.execution import JobExecutionContext


@shared_task(
    bind=True,
    name='app.artifact_registry.inventory.tasks.sync_artifact_registry_inventory',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_artifact_registry_inventory_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]],
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    context = JobExecutionContext(str(self.request.id), job_execution_id)
    started = perf_counter()
    total = len(targets)
    synced = 0
    projects = repositories = artifacts = tags = 0
    failures: list[dict[str, str]] = []
    context.start(
        message='Preparing Artifact Registry inventory synchronization.',
        total=total,
        percent=1,
        stage='Preparing Registry Inventory',
        target='Registry Estate',
    )
    for index, target in enumerate(targets, start=1):
        instance_id = int(target['integration_instance_id'])
        instance = IntegrationInstance.query.get(instance_id)
        if instance is None:
            failures.append({'instance': target['instance_name'], 'error': 'Registry integration no longer exists.'})
            continue
        context.checkpoint(
            current=index - 1,
            total=total,
            percent=min(5 + int(((index - 1) / max(total, 1)) * 90), 95),
            stage='Collecting Registry Inventory',
            target=instance.name,
            message=f'Collecting committed inventory from {instance.name}.',
        )
        try:
            result = sync_registry_instance(instance)
        except Exception as exc:
            failures.append({'instance': instance.name, 'error': str(exc)})
            continue
        synced += 1
        projects += int(result['projects'])
        repositories += int(result['repositories'])
        artifacts += int(result['artifacts'])
        tags += int(result['tags'])

    status = 'success' if not failures else ('warning' if synced else 'error')
    result = {
        'status': status,
        'requested_by_user_id': requested_by_user_id,
        'total_count': total,
        'synced_count': synced,
        'failed_count': len(failures),
        'project_count': projects,
        'repository_count': repositories,
        'artifact_count': artifacts,
        'tag_count': tags,
        'failures': failures,
        'finished_at': datetime.now(UTC).isoformat(),
        'duration_seconds': round(perf_counter() - started, 1),
    }
    context.checkpoint(
        current=total,
        total=total,
        percent=98,
        stage='Finalizing Registry Inventory',
        target='Registry Estate',
        message='Finalizing committed Artifact Registry inventory evidence.',
    )
    if failures and not synced:
        context.fail(
            'All eligible Registry sources failed inventory synchronization.',
            error_code='artifact_registry_inventory_failed',
        )
    else:
        context.succeed(
            result_summary=result,
            result_type='artifact_registry_inventory_sync',
            partial=bool(failures),
        )
    return result
