from __future__ import annotations

from datetime import UTC

from app.artifact_registry.eligibility import registry_inventory_eligibility
from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.registry import RegistryCollectionState, RegistryProject
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'


class NoEligibleRegistryTargets(RuntimeError):
    """Raised when no operationally eligible Registry provider can be synchronized."""


def build_registry_inventory_targets() -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    identities = (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.id.asc())
        .all()
    )
    for identity in identities:
        eligibility = registry_inventory_eligibility(identity)
        if not eligibility.eligible:
            continue
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
    confirm_empty_instance_id: int | None = None,
) -> tuple[JobExecution, bool]:
    from app.artifact_registry.tasks import sync_all_registry_task

    targets = build_registry_inventory_targets()
    if not targets:
        raise NoEligibleRegistryTargets(
            'No Registry provider has an operationally eligible validated read contract for inventory synchronization.'
        )
    reconciliation: dict[str, str | int] | None = None
    if confirm_empty_instance_id is not None:
        if trigger_type != 'manual' or requested_by_user_id is None:
            raise NoEligibleRegistryTargets(
                'Confirmed-empty Registry reconciliation requires an authenticated manual job.'
            )
        chosen = next(
            (target for target in targets if int(target['integration_instance_id']) == confirm_empty_instance_id),
            None,
        )
        if chosen is None:
            raise NoEligibleRegistryTargets('The selected Registry provider is no longer eligible for Inventory Sync.')
        state = RegistryCollectionState.query.filter_by(integration_instance_id=confirm_empty_instance_id).first()
        count = RegistryProject.query.filter_by(integration_instance_id=confirm_empty_instance_id).count()
        if state is None or state.last_committed_at is None or count <= 0:
            raise NoEligibleRegistryTargets('Only a previously committed, nonempty Registry may be confirmed empty.')
        committed = state.last_committed_at
        if committed.tzinfo is None:
            committed = committed.replace(tzinfo=UTC)
        reconciliation = {
            'integration_instance_id': confirm_empty_instance_id,
            'confirmed_by_user_id': requested_by_user_id,
            'previous_project_count': count,
            'previous_committed_at': committed.isoformat(),
        }
        targets = [chosen]
    return enqueue_canonical_job(
        task=sync_all_registry_task,
        task_kwargs={
            'requested_by_user_id': requested_by_user_id,
            'targets': targets,
            'empty_reconciliation': reconciliation,
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
        parameters=(
            {
                'scope': 'provider',
                'integration_instance_id': str(confirm_empty_instance_id),
                'reconciliation': 'confirmed_empty',
            }
            if reconciliation
            else {'scope': 'all'}
        ),
        payload={
            'total_count': len(targets),
            'targets': targets,
            'trigger_type': trigger_type,
            'empty_reconciliation': reconciliation,
        },
        max_attempts=3,
        dispatch_options=JobDispatchOptions(require_registered_worker=True),
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
    eligibility = registry_inventory_eligibility(identity)
    if not eligibility.eligible:
        raise NoEligibleRegistryTargets(eligibility.reason)

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
        dispatch_options=JobDispatchOptions(require_registered_worker=True),
    )
