from __future__ import annotations

from app.artifact_registry.security.tasks import sync_artifact_registry_security_task
from app.common.job_execution_contract import ARTIFACT_REGISTRY_SECURITY_SYNC_OPERATION
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.registry_artifact import RegistryCollectionState
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'
SUPPORTED_SECURITY_COLLECTORS = {'harbor'}


class NoEligibleRegistrySecurityTargets(RuntimeError):
    pass


def build_registry_security_targets() -> list[dict[str, str]]:
    instances = (
        IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry')
        .order_by(IntegrationInstance.id.asc())
        .all()
    )
    ids = [instance.id for instance in instances]
    inventory_states = {
        item.integration_instance_id: item
        for item in RegistryCollectionState.query.filter(
            RegistryCollectionState.integration_instance_id.in_(ids)
        ).all()
    } if ids else {}
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
        and item.provider_key in SUPPORTED_SECURITY_COLLECTORS
        and inventory_states.get(item.id) is not None
        and inventory_states[item.id].status == 'collected'
    ]


def enqueue_artifact_registry_security_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    targets = build_registry_security_targets()
    if not targets:
        raise NoEligibleRegistrySecurityTargets(
            'No validated Registry source with committed inventory is eligible for security synchronization.'
        )
    return enqueue_canonical_job(
        task=sync_artifact_registry_security_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
        job_type='artifact_registry_security',
        operation=ARTIFACT_REGISTRY_SECURITY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='registry',
        integration_instance_id=None,
        scope_type='registry_security_fleet',
        scope_key='all',
        resource_group='artifact-registry-security:global',
        parameters={'scope': 'all'},
        payload={'targets': targets, 'total_count': len(targets), 'trigger_type': trigger_type},
        max_attempts=3,
    )
