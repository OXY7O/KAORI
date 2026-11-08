from __future__ import annotations

from typing import Any

from app.artifact_registry.correlation_sync_jobs import (
    RegistryRuntimeCorrelationBlocked,
    correlation_prerequisites,
    enqueue_registry_runtime_correlation,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_RUNTIME_CORRELATION_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_registry_runtime_correlation(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    try:
        job, created = enqueue_registry_runtime_correlation(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except RegistryRuntimeCorrelationBlocked as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'A canonical Artifact Registry runtime correlation execution was queued.'
            if created
            else 'The request joined the active Artifact Registry runtime correlation execution.'
        ),
        job=job,
        created=created,
    )


def build_registry_runtime_correlation_context(policy: JobPolicy) -> dict[str, Any]:
    prerequisites = correlation_prerequisites()
    eligible = bool(prerequisites['eligible'])
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_runtime_correlation',
        JobExecution.operation == ARTIFACT_REGISTRY_RUNTIME_CORRELATION_OPERATION,
    )
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent[0] if recent else None

    return {
        **prerequisites,
        'eligible_target_count': 1 if eligible else 0,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active) if active is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Automatic Registry runtime correlation policy state.',
        },
        'readiness_state': {
            'label': 'Materialization Ready' if eligible else 'Blocked',
            'tone': 'normal' if eligible else 'warning',
            'icon': 'waypoints' if eligible else 'shield-alert',
            'description': (
                'Committed Registry and Kubernetes inventory are ready for DB-only correlation.'
                if eligible
                else 'Collect Registry artifacts and Kubernetes Pod inventory before correlation.'
            ),
        },
        'configuration_state': {
            'label': 'Execution Active' if active else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'execution_state': {
            'label': 'Execution Active' if active else ('Ready' if eligible else 'Blocked'),
            'tone': 'pending' if active else ('normal' if eligible else 'warning'),
            'icon': 'loader-circle' if active else ('circle-check' if eligible else 'shield-alert'),
            'description': (
                'Registry runtime correlation is active.'
                if active
                else (
                    'Digest-first runtime correlation can be rebuilt from committed evidence.'
                    if eligible
                    else 'Committed Registry and Kubernetes inventory are required.'
                )
            ),
        },
    }
