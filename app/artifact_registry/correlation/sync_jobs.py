from __future__ import annotations

from app.artifact_registry.correlation.tasks import materialize_artifact_registry_runtime_correlation_task
from app.common.inventory_generation import filter_current_generation
from app.common.job_execution_contract import ARTIFACT_REGISTRY_RUNTIME_CORRELATION_OPERATION
from app.models.job import JobExecution
from app.models.registry_artifact import RegistryArtifact
from app.models.inventory import PodInventory
from app.platform_operations.jobs.constants import WORKLOAD_STANDARD
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job

INVENTORY_QUEUE = 'inventory'


class RegistryRuntimeCorrelationBlocked(RuntimeError):
    pass


def correlation_prerequisites() -> dict[str, int | bool]:
    artifact_count = RegistryArtifact.query.count()
    pod_count = filter_current_generation(PodInventory.query, PodInventory).count()
    return {
        'artifact_count': artifact_count,
        'pod_count': pod_count,
        'eligible': bool(artifact_count and pod_count),
    }


def enqueue_registry_runtime_correlation(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    prerequisites = correlation_prerequisites()
    if not prerequisites['eligible']:
        raise RegistryRuntimeCorrelationBlocked(
            'Committed Artifact Registry artifacts and Kubernetes Pod inventory are both required before runtime correlation.'
        )
    return enqueue_canonical_job(
        task=materialize_artifact_registry_runtime_correlation_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id},
        job_type='artifact_registry_runtime_correlation',
        operation=ARTIFACT_REGISTRY_RUNTIME_CORRELATION_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type=None,
        integration_instance_id=None,
        scope_type='registry_kubernetes_correlation',
        scope_key='all',
        resource_group='artifact-registry-runtime-correlation:global',
        parameters={'scope': 'all'},
        payload={'trigger_type': trigger_type, **prerequisites},
        max_attempts=3,
    )
