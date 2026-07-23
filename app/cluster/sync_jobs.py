from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.cluster.individual_sync_state import register_individual_sync_task
from app.cluster.sync_state import store_cluster_sync_metadata
from app.cluster.tasks import sync_all_clusters_task, sync_single_cluster_task
from app.jobs.constants import WORKLOAD_STANDARD
from app.jobs.dispatcher import enqueue_canonical_job
from app.jobs.service import acquire_resource_admission_locks
from app.models.cluster import Cluster
from app.models.job import JobExecution
from app.models.kubernetes import KubernetesConnection

logger = logging.getLogger(__name__)

INVENTORY_QUEUE = 'inventory'


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def enqueue_all_cluster_inventory_sync(*, requested_by_user_id: int) -> tuple[JobExecution, bool]:
    total_count = Cluster.query.count()
    job, created = enqueue_canonical_job(
        task=sync_all_clusters_task,
        task_kwargs={'requested_by_user_id': requested_by_user_id},
        job_type='kubernetes_inventory',
        operation='inventory_sync_all',
        queue_name=INVENTORY_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        provider_type='kubernetes',
        provider_instance_id=None,
        scope_type='kubernetes_fleet',
        scope_key='all',
        resource_group='kubernetes-inventory:global',
        parameters={'scope': 'all', 'cluster_count': total_count},
        payload={'total_count': total_count},
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
    try:
        store_cluster_sync_metadata(task_id=str(job.celery_task_id), metadata=metadata)
    except Exception:
        logger.exception('Could not persist supplemental global inventory-sync metadata.')
    return job, created


def enqueue_cluster_inventory_sync(
    *,
    cluster: Cluster,
    requested_by_user_id: int,
) -> tuple[JobExecution, bool]:
    resource_group = f'kubernetes-cluster:{cluster.id}'
    acquire_resource_admission_locks(resource_group)
    current_cluster = Cluster.query.filter_by(id=cluster.id).populate_existing().first()
    if current_cluster is None:
        raise RuntimeError('The Kubernetes cluster was deleted before KAORI could admit the job.')
    connection: KubernetesConnection | None = current_cluster.kubernetes_connection
    if connection is None:
        raise RuntimeError('The cluster has no canonical Kubernetes connection.')
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
        provider_type='kubernetes',
        provider_instance_id=connection.id,
        scope_type='kubernetes_cluster',
        scope_key=str(cluster.id),
        resource_group=resource_group,
        parameters={'cluster_id': str(cluster.id), 'scope': 'single_cluster'},
        payload={'cluster_id': str(current_cluster.id), 'cluster_name': current_cluster.name},
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
    try:
        register_individual_sync_task(
            task_id=str(job.celery_task_id),
            user_id=requested_by_user_id,
            metadata=metadata,
        )
    except Exception:
        logger.exception('Could not persist supplemental cluster inventory-sync metadata.')
    return job, created
