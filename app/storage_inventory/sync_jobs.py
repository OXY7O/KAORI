from __future__ import annotations

from app.common.job_execution_contract import OBJECT_STORAGE_INVENTORY_SYNC_OPERATION
from app.jobs.constants import WORKLOAD_STANDARD
from app.jobs.dispatcher import enqueue_canonical_job
from app.models.job import JobExecution
from app.models.minio import MinioInstance
from app.storage_inventory.tasks import sync_all_object_storage_task

INVENTORY_QUEUE = 'inventory'


class NoEligibleObjectStorageTargets(RuntimeError):
    """Raised when no validated managed object-storage system can be synchronized."""


def build_object_storage_inventory_targets() -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    instances = MinioInstance.query.order_by(MinioInstance.id.asc()).all()
    for instance in instances:
        canonical = instance.integration_instance
        if not canonical.enabled or canonical.lifecycle_status != 'active':
            continue
        if instance.readiness_status != 'ready':
            continue
        targets.append(
            {
                'instance_id': str(instance.id),
                'instance_name': instance.name,
                'system_id': str(instance.object_storage_system_id),
                'system_name': instance.object_storage_system.name,
            }
        )
    return targets


def enqueue_all_object_storage_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    targets = build_object_storage_inventory_targets()
    if not targets:
        raise NoEligibleObjectStorageTargets(
            'No object-storage system is enabled and Ready for inventory synchronization.'
        )
    job, created = enqueue_canonical_job(
        task=sync_all_object_storage_task,
        task_kwargs={
            'requested_by_user_id': requested_by_user_id,
            'targets': targets,
        },
        job_type='object_storage_inventory',
        operation=OBJECT_STORAGE_INVENTORY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        provider_type='minio',
        provider_instance_id=None,
        scope_type='object_storage_fleet',
        scope_key='all',
        resource_group='object-storage-inventory:global',
        parameters={'scope': 'all'},
        payload={
            'total_count': len(targets),
            'targets': targets,
            'trigger_type': trigger_type,
        },
        max_attempts=3,
    )
    return job, created
