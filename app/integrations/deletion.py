from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_

from app.common.job_execution_contract import KUBERNETES_INVENTORY_SYNC_OPERATION
from app.models.job import JobExecution
from app.models.secret_reveal import SecretRevealRequest
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES


@dataclass(frozen=True)
class DeletionGuard:
    blocked: bool
    reasons: tuple[str, ...]
    active_jobs: int = 0
    active_requests: int = 0

    @property
    def message(self) -> str:
        return ' '.join(self.reasons)


class DeletionBlocked(ValueError):
    """Raised when KAORI cannot safely delete an integration identity."""

    def __init__(self, guard: DeletionGuard) -> None:
        super().__init__(guard.message)
        self.guard = guard


def provider_active_job_count(*, integration_type: str, integration_instance_id: int) -> int:
    return (
        JobExecution.query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .filter(
            or_(
                (
                    (JobExecution.integration_type == integration_type)
                    & (JobExecution.integration_instance_id == integration_instance_id)
                ),
                JobExecution.resource_group == f'integration:{integration_type}:{integration_instance_id}',
            )
        )
        .count()
    )


def asset_owner_active_job_count(
    *,
    integration_type: str,
    integration_instance_id: int,
    asset_type: str,
    asset_key: str,
) -> int:
    """Count active jobs referencing an asset-owning provider or its managed asset."""
    return (
        JobExecution.query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .filter(
            or_(
                (
                    (JobExecution.integration_type == integration_type)
                    & (JobExecution.integration_instance_id == integration_instance_id)
                ),
                (JobExecution.scope_type == asset_type) & (JobExecution.scope_key == str(asset_key)),
                JobExecution.resource_group == f'integration:{integration_type}:{integration_instance_id}',
                JobExecution.resource_group == f'{asset_type}:{asset_key}',
            )
        )
        .count()
    )


def kubernetes_active_job_count(*, integration_instance_id: int, cluster_id: str) -> int:
    return (
        JobExecution.query.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES))
        .filter(
            or_(
                (
                    (JobExecution.integration_type == 'container_orchestrator')
                    & (JobExecution.integration_instance_id == integration_instance_id)
                ),
                ((JobExecution.scope_type == 'kubernetes_cluster') & (JobExecution.scope_key == cluster_id)),
                (
                    (JobExecution.integration_type == 'container_orchestrator')
                    & (JobExecution.operation == KUBERNETES_INVENTORY_SYNC_OPERATION)
                ),
                JobExecution.resource_group == f'kubernetes-cluster:{cluster_id}',
                JobExecution.resource_group == f'integration:container_orchestrator:{integration_instance_id}',
            )
        )
        .count()
    )


def kubernetes_active_reveal_request_count(*, cluster_id: str) -> int:
    return SecretRevealRequest.query.filter(
        SecretRevealRequest.cluster_id == cluster_id,
        SecretRevealRequest.status.in_(('pending', 'approved')),
    ).count()


def provider_deletion_guard(*, integration_type: str, integration_instance_id: int) -> DeletionGuard:
    active_jobs = provider_active_job_count(
        integration_type=integration_type,
        integration_instance_id=integration_instance_id,
    )
    reasons: list[str] = []
    if active_jobs:
        reasons.append(
            f'{active_jobs} active KAORI job(s) still reference this connection. '
            'Wait for completion or cancel an eligible queued job before deleting it.'
        )
    return DeletionGuard(
        blocked=bool(reasons),
        reasons=tuple(reasons),
        active_jobs=active_jobs,
    )


def asset_owner_deletion_guard(
    *,
    integration_type: str,
    integration_instance_id: int,
    asset_type: str,
    asset_key: str,
) -> DeletionGuard:
    """Guard deletion of a provider that owns one managed operational asset."""
    active_jobs = asset_owner_active_job_count(
        integration_type=integration_type,
        integration_instance_id=integration_instance_id,
        asset_type=asset_type,
        asset_key=asset_key,
    )
    reasons: list[str] = []
    if active_jobs:
        reasons.append(
            f'{active_jobs} active KAORI job(s) still reference this connection or managed asset. '
            'Wait for completion or cancel an eligible queued job before deleting it.'
        )
    return DeletionGuard(
        blocked=bool(reasons),
        reasons=tuple(reasons),
        active_jobs=active_jobs,
    )


def kubernetes_deletion_guard(*, integration_instance_id: int, cluster_id: str) -> DeletionGuard:
    active_jobs = kubernetes_active_job_count(
        integration_instance_id=integration_instance_id,
        cluster_id=cluster_id,
    )
    active_requests = kubernetes_active_reveal_request_count(cluster_id=cluster_id)
    reasons: list[str] = []
    if active_jobs:
        reasons.append(
            f'{active_jobs} active KAORI job(s) still reference this Kubernetes connection. '
            'Wait for completion or cancel an eligible queued job before deleting it.'
        )
    if active_requests:
        reasons.append(
            f'{active_requests} pending or approved Protected Secret Reveal request(s) still depend on this cluster. '
            'Resolve or expire those requests before deleting the connection.'
        )
    return DeletionGuard(
        blocked=bool(reasons),
        reasons=tuple(reasons),
        active_jobs=active_jobs,
        active_requests=active_requests,
    )
