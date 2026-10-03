from __future__ import annotations

from app.artifact_registry.inventory.tasks import sync_artifact_registry_inventory_task
from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'
SUPPORTED_COLLECTORS = {'harbor'}


class NoEligibleRegistryTargets(RuntimeError):
    pass


def build_registry_inventory_targets() -> list[dict[str, str]]:
    instances = (
        IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry')
        .order_by(IntegrationInstance.id.asc())
        .all()
    )
    return [
        {
            'integration_instance_id': str(item.id),
            'instance_name': item.name,
            'provider_key': item.provider_key,
        }
        for item in instances
        if item.enabled
        and item.lifecycle_status == 'active'
        and item.readiness_status in {'ready', 'degraded'}
        and item.provider_key in SUPPORTED_COLLECTORS
    ]


def enqueue_artifact_registry_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    targets = build_registry_inventory_targets()
    if not targets:
        raise NoEligibleRegistryTargets(
            'No enabled Ready/Degraded Registry integration has a qualified inventory collector.'
        )
    return enqueue_canonical_job(
        task=sync_artifact_registry_inventory_task,
        task_kwargs={
            'requested_by_user_id': requested_by_user_id,
            'targets': targets,
        },
        job_type='artifact_registry_inventory',
        operation=ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='registry',
        integration_instance_id=None,
        scope_type='registry_fleet',
        scope_key='all',
        resource_group='artifact-registry-inventory:global',
        parameters={'scope': 'all'},
        payload={'targets': targets, 'total_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=3,
    )
