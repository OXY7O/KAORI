from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.cluster.individual_sync_state import register_individual_sync_task
from app.cluster.sync_state import store_cluster_sync_metadata
from app.cluster.tasks import sync_all_clusters_task, sync_single_cluster_task
from app.common.job_execution_contract import KUBERNETES_INVENTORY_SYNC_OPERATION
from app.integrations.kubernetes.resolver import connection_for_cluster
from app.jobs.constants import WORKLOAD_STANDARD
from app.jobs.dispatcher import enqueue_canonical_job
from app.jobs.service import acquire_resource_admission_locks
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.models.kubernetes import KubernetesConnection

logger = logging.getLogger(__name__)

INVENTORY_QUEUE = 'inventory'


class NoEligibleInventoryTargets(RuntimeError):
    """Raised when no cluster has an enabled canonical Kubernetes binding."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_fleet_inventory_targets(*, log_skipped: bool = True) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    for cluster in clusters:
        try:
            connection_for_cluster(cluster)
        except RuntimeError:
            if log_skipped:
                logger.warning(
                    'Skipping cluster %s from fleet inventory sync because no enabled canonical '
                    'Kubernetes binding is available.',
                    cluster.id,
                )
            continue
        targets.append({'cluster_id': str(cluster.id), 'cluster_name': cluster.name})
    return targets


def enqueue_all_cluster_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    targets = build_fleet_inventory_targets()
    total_count = len(targets)
    if not targets:
        raise NoEligibleInventoryTargets('No registered cluster has an enabled canonical Kubernetes binding.')
    job, created = enqueue_canonical_job(
        task=sync_all_clusters_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id, 'targets': targets},
        job_type='kubernetes_inventory',
        operation=KUBERNETES_INVENTORY_SYNC_OPERATION,
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='container_orchestrator',
        integration_instance_id=None,
        scope_type='kubernetes_fleet',
        scope_key='all',
        resource_group='kubernetes-inventory:global',
        parameters={'scope': 'all'},
        payload={'total_count': total_count, 'targets': targets, 'trigger_type': trigger_type},
        max_attempts=3,
    )
    metadata = {
        'requested_by_user_id': requested_by_user_id,
        'created_at': job.queued_at.isoformat() if job.queued_at else _now_iso(),
        'total_count': total_count,
        'processed_count': job.progress_current,
        'synced_count': 0,
        'failed_count': 0,
        'current_cluster_name': None,
        'job_execution_id': job.id,
    }
    if created:
        try:
            store_cluster_sync_metadata(task_id=str(job.celery_task_id), metadata=metadata)
        except Exception:
            logger.exception('Could not persist supplemental global inventory-sync metadata.')
    return job, created


def enqueue_cluster_inventory_sync(
    *,
    cluster: Cluster,
    requested_by_user_id: int | None,
    trigger_type: str = 'manual',
) -> tuple[JobExecution, bool]:
    acquire_resource_admission_locks(f'kubernetes-cluster:{cluster.id}')
    current_cluster = Cluster.query.filter_by(id=cluster.id).populate_existing().first()
    if current_cluster is None:
        raise LookupError('The selected Kubernetes cluster no longer exists.')
    connection: KubernetesConnection = connection_for_cluster(current_cluster)
    cluster = current_cluster
    job, created = enqueue_canonical_job(
        task=sync_single_cluster_task,
        task_kwargs={
            'cluster_id': cluster.id,
            'requested_by_user_id': requested_by_user_id,
        },
        job_type='kubernetes_inventory',
        operation='inventory_sync_cluster',
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        integration_type='container_orchestrator',
        integration_instance_id=connection.integration_instance_id,
        scope_type='kubernetes_cluster',
        scope_key=str(cluster.id),
        resource_group=f'kubernetes-cluster:{cluster.id}',
        parameters={'cluster_id': str(cluster.id), 'scope': 'single_cluster'},
        payload={'cluster_id': str(cluster.id), 'cluster_name': cluster.name, 'trigger_type': trigger_type},
        max_attempts=3,
    )
    created_at = job.queued_at.isoformat() if job.queued_at else _now_iso()
    metadata: dict[str, Any] = {
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'requested_by_user_id': requested_by_user_id,
        'created_at': created_at,
        'started_at': created_at,
        'status': 'info',
        'title': 'Cluster inventory sync in progress',
        'message': f'Synchronizing Kubernetes inventory for {cluster.name}.',
        'job_execution_id': job.id,
    }
    if requested_by_user_id is not None:
        try:
            register_individual_sync_task(
                task_id=str(job.celery_task_id),
                user_id=requested_by_user_id,
                metadata=metadata,
            )
        except Exception:
            logger.exception('Could not persist supplemental cluster inventory-sync metadata.')
    return job, created
