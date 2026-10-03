from __future__ import annotations

from typing import Any

from app.artifact_registry.sync_jobs import (
    NoEligibleRegistryTargets,
    build_registry_inventory_targets,
    enqueue_all_registry_inventory_sync,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_registry_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    try:
        job, created = enqueue_all_registry_inventory_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except NoEligibleRegistryTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'A canonical Artifact Registry inventory execution was queued.'
            if created
            else 'The request joined the active Artifact Registry inventory execution.'
        ),
        job=job,
        created=created,
    )


def _present(job: JobExecution | None) -> dict[str, Any] | None:
    return present_job_execution(job) if job is not None else None


def build_registry_inventory_sync_context(policy: JobPolicy) -> dict[str, Any]:
    registered_count = IntegrationInstance.query.filter_by(integration_type='registry').count()
    eligible_targets = build_registry_inventory_targets()
    eligible_count = len(eligible_targets)
    blocked_count = max(registered_count - eligible_count, 0)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_inventory',
        JobExecution.operation == ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION,
    )
    active_job = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest_job = recent_jobs[0] if recent_jobs else None
    return {
        'registered_system_count': registered_count,
        'eligible_system_count': eligible_count,
        'eligible_target_count': eligible_count,
        'blocked_system_count': blocked_count,
        'eligible_targets': eligible_targets,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': _present(active_job),
        'latest_job': _present(latest_job),
        'recent_jobs': [present_job_execution(job) for job in recent_jobs],
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Automatic Registry reconciliation policy state.',
        },
        'readiness_state': {
            'label': 'Sync Eligible' if eligible_count else 'Blocked',
            'tone': 'normal' if eligible_count else 'warning',
            'icon': 'link-2' if eligible_count else 'shield-alert',
            'description': (
                'Ready Registry providers are eligible for committed reconciliation.'
                if eligible_count
                else 'No Ready Registry provider is available for synchronization.'
            ),
        },
        'configuration_state': {
            'label': 'Execution Active' if active_job else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active_job else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active_job else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'execution_state': {
            'label': 'Execution Active' if active_job else ('Ready' if eligible_count else 'Blocked'),
            'tone': 'pending' if active_job else ('normal' if eligible_count else 'warning'),
            'icon': 'loader-circle' if active_job else ('circle-check' if eligible_count else 'shield-alert'),
            'description': (
                'An Artifact Registry inventory job is active.'
                if active_job
                else (
                    'The eligible Registry estate is ready to synchronize.'
                    if eligible_count
                    else 'Complete Full Validation for an enabled Registry provider before syncing.'
                )
            ),
        },
    }
