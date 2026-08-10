from __future__ import annotations

import logging
from typing import Any

from app.governance.tls_certificates.constants import (
    TLS_SYNC_JOB_TYPE,
    TLS_SYNC_OPERATION,
    TLS_SYNC_QUEUE,
)
from app.governance.tls_certificates.tasks import sync_tls_certificates_task
from app.integrations.kubernetes.resolver import connection_for_cluster
from app.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_STANDARD
from app.jobs.dispatcher import enqueue_canonical_job
from app.jobs.service import acquire_resource_admission_locks, attach_job_subscriber
from app.models.cluster import Cluster
from app.models.job import JobExecution

logger = logging.getLogger(__name__)



class NoEligibleTLSCertificateTargets(RuntimeError):
    """Raised when no cluster can be collected through a canonical Kubernetes binding."""


def build_tls_certificate_targets(*, cluster_id: str | None = None) -> list[dict[str, str]]:
    query = Cluster.query
    if cluster_id:
        query = query.filter(Cluster.id == cluster_id)

    targets: list[dict[str, str]] = []
    for cluster in query.order_by(Cluster.name.asc(), Cluster.id.asc()).all():
        try:
            connection_for_cluster(cluster)
        except RuntimeError:
            logger.warning(
                'Skipping cluster %s from TLS certificate sync because no enabled canonical '
                'Kubernetes binding is available.',
                cluster.id,
            )
            continue
        targets.append({'cluster_id': str(cluster.id), 'cluster_name': cluster.name})
    return targets


def _active_tls_sync_jobs() -> list[JobExecution]:
    return (
        JobExecution.query.filter(
            JobExecution.job_type == TLS_SYNC_JOB_TYPE,
            JobExecution.operation == TLS_SYNC_OPERATION,
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(JobExecution.created_at.asc(), JobExecution.id.asc())
        .all()
    )


def _job_target_ids(job: JobExecution) -> set[str]:
    payload = job.payload_json or {}
    return {
        str(target.get('cluster_id'))
        for target in payload.get('targets') or []
        if isinstance(target, dict) and str(target.get('cluster_id') or '').strip()
    }


def _is_fleet_job(job: JobExecution) -> bool:
    payload = job.payload_json or {}
    return str(payload.get('scope') or '').strip() == 'all_clusters' or job.scope_key == 'all'


def _resolve_overlap(
    *,
    targets: list[dict[str, str]],
    cluster_id: str | None,
    requested_by_user_id: int | None,
) -> tuple[list[dict[str, str]], JobExecution | None]:
    """Avoid duplicate collection for overlapping fleet and cluster requests."""
    active_jobs = _active_tls_sync_jobs()
    if not active_jobs:
        return targets, None

    if cluster_id:
        selected_id = str(cluster_id)
        for job in active_jobs:
            if _is_fleet_job(job) or selected_id in _job_target_ids(job):
                attach_job_subscriber(job, requested_by_user_id)
                return [], job
        return targets, None

    for job in active_jobs:
        if _is_fleet_job(job):
            attach_job_subscriber(job, requested_by_user_id)
            return [], job

    busy_cluster_ids = set().union(*(_job_target_ids(job) for job in active_jobs))
    remaining_targets = [
        target for target in targets if str(target['cluster_id']) not in busy_cluster_ids
    ]
    if remaining_targets:
        return remaining_targets, None

    job = active_jobs[0]
    attach_job_subscriber(job, requested_by_user_id)
    return [], job


def enqueue_tls_certificate_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    cluster_id: str | None = None,
) -> tuple[JobExecution, bool]:
    targets = build_tls_certificate_targets(cluster_id=cluster_id)
    if not targets:
        raise NoEligibleTLSCertificateTargets(
            'No selected cluster has an enabled canonical Kubernetes binding.'
            if cluster_id
            else 'No registered cluster has an enabled canonical Kubernetes binding.'
        )

    selected_cluster_id = str(cluster_id or '').strip() or None
    requested_target_count = len(targets)
    acquire_resource_admission_locks('tls-certificate-inventory:admission')
    targets, overlapping_job = _resolve_overlap(
        targets=targets,
        cluster_id=selected_cluster_id,
        requested_by_user_id=requested_by_user_id,
    )
    if overlapping_job is not None:
        return overlapping_job, False

    is_fleet_subset = not selected_cluster_id and len(targets) < requested_target_count
    scope_type = (
        'kubernetes_cluster'
        if selected_cluster_id
        else 'kubernetes_fleet_subset'
        if is_fleet_subset
        else 'kubernetes_fleet'
    )
    scope_key = selected_cluster_id or ('subset' if is_fleet_subset else 'all')
    resource_group = (
        f'tls-certificate-inventory:cluster:{selected_cluster_id}'
        if selected_cluster_id
        else 'tls-certificate-inventory:fleet-subset'
        if is_fleet_subset
        else 'tls-certificate-inventory:global'
    )
    parameters: dict[str, Any] = {
        'scope': (
            'selected_cluster'
            if selected_cluster_id
            else 'fleet_subset'
            if is_fleet_subset
            else 'all_clusters'
        ),
        'cluster_id': selected_cluster_id,
        'target_cluster_ids': [target['cluster_id'] for target in targets],
    }
    payload = {
        **parameters,
        'trigger_type': trigger_type,
        'target_count': len(targets),
        'targets': targets,
    }

    return enqueue_canonical_job(
        task=sync_tls_certificates_task,
        task_kwargs={
            'targets': targets,
            'requested_by_user_id': requested_by_user_id,
            'trigger_type': trigger_type,
        },
        job_type=TLS_SYNC_JOB_TYPE,
        operation=TLS_SYNC_OPERATION,
        queue_name=TLS_SYNC_QUEUE,
        workload_class=WORKLOAD_STANDARD,
        requested_by_user_id=requested_by_user_id,
        provider_type='kubernetes',
        provider_instance_id=None,
        scope_type=scope_type,
        scope_key=scope_key,
        resource_group=resource_group,
        parameters=parameters,
        payload=payload,
        max_attempts=3,
    )
