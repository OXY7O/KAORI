from __future__ import annotations

from app.artifact_registry.eligibility import registry_inventory_eligibility
from app.artifact_registry.security.providers import registered_registry_security_collectors
from app.common.job_execution_contract import ARTIFACT_REGISTRY_SECURITY_SYNC_OPERATION
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.registry import RegistryCollectionState
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'


class NoEligibleRegistrySecurityTargets(RuntimeError):
    """Raised when no committed Registry source can refresh security evidence."""


def build_registry_security_targets() -> list[dict[str, str]]:
    provider_keys = {collector.provider_key for collector in registered_registry_security_collectors()}
    identities = (
        IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.id.asc())
        .all()
    )
    targets: list[dict[str, str]] = []
    for identity in identities:
        if identity.provider_key not in provider_keys:
            continue
        state = RegistryCollectionState.query.filter_by(
            integration_instance_id=int(identity.id)
        ).first()
        if state is None or state.status != 'ready' or state.last_committed_at is None:
            continue
        if not registry_inventory_eligibility(identity).eligible:
            continue
        targets.append(
            {
                'integration_instance_id': str(identity.id),
                'instance_name': identity.name,
                'provider_key': identity.provider_key,
            }
        )
    return targets


def enqueue_all_registry_security_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    from app.artifact_registry.security.tasks import sync_all_registry_security_task

    targets = build_registry_security_targets()
    if not targets:
        raise NoEligibleRegistrySecurityTargets(
            'No Registry provider with committed inventory is eligible for security synchronization.'
        )
    return enqueue_canonical_job(
        task=sync_all_registry_security_task,
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
        payload={'total_count': len(targets), 'targets': targets, 'trigger_type': trigger_type},
        max_attempts=3,
        dispatch_options=JobDispatchOptions(require_registered_worker=True),
    )
