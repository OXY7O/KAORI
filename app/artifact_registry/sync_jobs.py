from __future__ import annotations

from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'


class NoEligibleRegistryTargets(RuntimeError):
    """Raised when no validated Registry provider can be synchronized."""


def build_registry_inventory_targets() -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    identities = (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationInstance.readiness_status == 'ready',
        )
        .order_by(IntegrationInstance.id.asc())
        .all()
    )
    for identity in identities:
        targets.append(
            {
                'integration_instance_id': str(identity.id),
                'instance_name': identity.name,
                'provider_key': identity.provider_key,
            }
        )
    return targets


def enqueue_all_registry_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    from app.artifact_registry.tasks import sync_all_registry_task

    targets = build_registry_inventory_targets()
    if not targets:
        raise NoEligibleRegistryTargets(
            'No Registry provider is enabled and Ready for inventory synchronization.'
        )
    return enqueue_canonical_job(
        task=sync_all_registry_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
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
        payload={'total_count': len(targets), 'targets': targets, 'trigger_type': trigger_type},
        max_attempts=3,
    )



def enqueue_registry_target_refresh(
    *,
    integration_instance_id: int,
    requested_by_user_id: int | None,
    trigger_type: str,
    scope_hint: dict[str, str | None] | None = None,
) -> tuple[JobExecution, bool]:
    """Fast-path refresh for one Registry provider; scheduled fleet sync remains repair authority."""

    from app.artifact_registry.tasks import sync_all_registry_task

    identity = IntegrationInstance.query.filter_by(
        id=integration_instance_id,
        integration_type='registry',
    ).first()
    if identity is None:
        raise NoEligibleRegistryTargets('The Registry provider no longer exists.')
    if not identity.enabled or identity.lifecycle_status != 'active' or identity.readiness_status != 'ready':
        raise NoEligibleRegistryTargets('The Registry provider is not enabled and Ready for reconciliation.')

    target = {
        'integration_instance_id': str(identity.id),
        'instance_name': identity.name,
        'provider_key': identity.provider_key,
    }
    parameters = {
        'scope': 'provider',
        'integration_instance_id': str(identity.id),
        'scope_hint': dict(scope_hint or {}),
    }
    return enqueue_canonical_job(
        task=sync_all_registry_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': [target]},
        job_type='artifact_registry_inventory',
        operation=ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='registry',
        integration_instance_id=identity.id,
        scope_type='registry_instance',
        scope_key=str(identity.id),
        resource_group=f'artifact-registry-inventory:{identity.id}',
        parameters=parameters,
        payload={
            'total_count': 1,
            'targets': [target],
            'trigger_type': trigger_type,
            'scope_hint': dict(scope_hint or {}),
        },
        max_attempts=3,
    )
