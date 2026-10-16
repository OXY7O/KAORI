from __future__ import annotations

from datetime import UTC

from app.common.job_execution_contract import OBJECT_STORAGE_INVENTORY_SYNC_OPERATION
from app.models.job import JobExecution
from app.models.minio import MinioInstance
from app.models.object_storage import ObjectStorageBucket, ObjectStorageSystem
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job
from app.storage.object_storage.inventory.tasks import sync_all_object_storage_task

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
    confirm_empty_system_id: str | None = None,
) -> tuple[JobExecution, bool]:
    targets = build_object_storage_inventory_targets()
    if not targets:
        raise NoEligibleObjectStorageTargets(
            'No object-storage system is enabled and Ready for inventory synchronization.'
        )
    reconciliation: dict[str, str | int] | None = None
    if confirm_empty_system_id is not None:
        if trigger_type != 'manual' or requested_by_user_id is None:
            raise NoEligibleObjectStorageTargets(
                'A confirmed-empty inventory reconciliation requires an authenticated manual job.'
            )
        target = next((row for row in targets if row['system_id'] == confirm_empty_system_id), None)
        if target is None:
            raise NoEligibleObjectStorageTargets(
                'The selected system is no longer eligible for Object Storage Inventory Sync.'
            )
        system = ObjectStorageSystem.query.filter_by(id=confirm_empty_system_id).first()
        previous_count = ObjectStorageBucket.query.filter_by(object_storage_system_id=confirm_empty_system_id).count()
        if system is None or system.inventory_observed_at is None or previous_count <= 0:
            raise NoEligibleObjectStorageTargets(
                'Only a previously observed, nonempty system can be reconciled as empty.'
            )
        previous_at = system.inventory_observed_at
        if previous_at.tzinfo is None:
            previous_at = previous_at.replace(tzinfo=UTC)
        reconciliation = {
            'system_id': confirm_empty_system_id,
            'system_name': target['system_name'],
            'confirmed_by_user_id': requested_by_user_id,
            'previous_bucket_count': previous_count,
            'previous_inventory_observed_at': previous_at.isoformat(),
        }
        # The explicit recovery request must never synchronize unrelated fleet members.
        targets = [target]
    job, created = enqueue_canonical_job(
        task=sync_all_object_storage_task,
        task_kwargs={
            'requested_by_user_id': requested_by_user_id,
            'targets': targets,
            'empty_reconciliation': reconciliation,
        },
        job_type='object_storage_inventory',
        operation=OBJECT_STORAGE_INVENTORY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='object_storage',
        integration_instance_id=None,
        scope_type='object_storage_fleet',
        scope_key='all',
        resource_group='object-storage-inventory:global',
        parameters=(
            {'scope': 'system', 'system_id': confirm_empty_system_id, 'reconciliation': 'confirmed_empty'}
            if reconciliation is not None
            else {'scope': 'all'}
        ),
        payload={
            'total_count': len(targets),
            'targets': targets,
            'trigger_type': trigger_type,
            'empty_reconciliation': reconciliation,
        },
        max_attempts=3,
    )
    return job, created
