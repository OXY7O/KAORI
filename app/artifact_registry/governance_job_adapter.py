from __future__ import annotations

from typing import Any

from app.artifact_registry.governance_sync_jobs import (
    NoEligibleRegistryGovernanceTargets,
    build_registry_governance_targets,
    enqueue_all_registry_governance_sync,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_GOVERNANCE_SYNC_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval
from app.platform_operations.jobs.policies.service import get_or_create_job_policy

GOVERNANCE_SYNC_JOB_KEY = 'artifact_registry.governance.sync'
GOVERNANCE_SYNC_JOB_TYPE = 'artifact_registry_governance'
GOVERNANCE_SYNC_OPERATION = ARTIFACT_REGISTRY_GOVERNANCE_SYNC_OPERATION
_SUCCESS_STATUSES = ('succeeded', 'partially_succeeded')


def dispatch_registry_governance_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    try:
        job, created = enqueue_all_registry_governance_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except NoEligibleRegistryGovernanceTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'A canonical Artifact Registry governance execution was queued.'
            if created
            else 'The request joined the active Artifact Registry governance execution.'
        ),
        job=job,
        created=created,
    )


def _present(job: JobExecution | None) -> dict[str, Any] | None:
    return present_job_execution(job) if job is not None else None


def get_registry_governance_sync_job(public_id: str) -> JobExecution | None:
    return (
        JobExecution.query.filter(
            JobExecution.job_type == GOVERNANCE_SYNC_JOB_TYPE,
            JobExecution.operation == GOVERNANCE_SYNC_OPERATION,
            JobExecution.public_id == public_id,
        )
        .order_by(JobExecution.id.desc())
        .first()
    )


def build_registry_governance_sync_state(*, policy: JobPolicy | None = None) -> dict[str, Any]:
    resolved_policy = policy or get_or_create_job_policy(GOVERNANCE_SYNC_JOB_KEY)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == GOVERNANCE_SYNC_JOB_TYPE,
        JobExecution.operation == GOVERNANCE_SYNC_OPERATION,
    )
    active_job = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(50).all()
    latest_job = recent_jobs[0] if recent_jobs else None
    latest_success = next((item for item in recent_jobs if item.status in _SUCCESS_STATUSES), None)

    if active_job is not None and active_job.status == 'queued':
        label, tone, icon = 'Queued', 'pending', 'clock-3'
        helper = active_job.progress_message or 'Waiting for the inventory worker to start Governance Sync.'
    elif active_job is not None:
        label, tone, icon = 'Syncing', 'pending', 'loader-circle'
        helper = active_job.progress_message or 'Registry governance evidence is refreshing on the inventory worker.'
    elif latest_job is not None and latest_job.status == 'failed':
        label, tone, icon = 'Sync Failed', 'critical', 'circle-x'
        helper = 'The latest Governance Sync failed. Previous committed governance evidence remains readable.'
    elif latest_success is None:
        label, tone, icon = 'Not Collected', 'warning', 'clock-alert'
        helper = 'Run Governance Sync to collect committed provider policy and replication evidence.'
    else:
        label, tone, icon = 'Ready', 'normal', 'circle-check'
        helper = 'Committed Governance evidence is available. Sync again when fresher provider evidence is needed.'

    return {
        'label': label,
        'tone': tone,
        'icon': icon,
        'helper': helper,
        'is_active': active_job is not None,
        'active_job_public_id': active_job.public_id if active_job is not None else None,
        'active_job': _present(active_job),
        'latest_job': _present(latest_job),
        'last_success_at': latest_success.completed_at if latest_success is not None else None,
        'last_success_label': present_user_datetime(
            latest_success.completed_at if latest_success is not None else None,
            empty='Never',
        ),
        'automatic_enabled': bool(resolved_policy.enabled),
        'automatic_label': 'Enabled' if resolved_policy.enabled else 'Manual Only',
        'interval_label': present_interval(resolved_policy.interval_minutes),
        'next_run_at': resolved_policy.next_run_at,
        'next_run_label': present_user_datetime(resolved_policy.next_run_at, empty='Not Scheduled'),
    }


def build_registry_governance_sync_context(policy: JobPolicy) -> dict[str, Any]:
    registered_count = IntegrationInstance.query.filter_by(integration_type='registry').count()
    eligible_targets = build_registry_governance_targets()
    eligible_count = len(eligible_targets)
    blocked_count = max(registered_count - eligible_count, 0)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_governance',
        JobExecution.operation == ARTIFACT_REGISTRY_GOVERNANCE_SYNC_OPERATION,
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
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(latest_job) if latest_job is not None else None,
        'recent_jobs': [present_job_execution(job) for job in recent_jobs],
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Automatic Registry governance refresh policy state.',
        },
        'readiness_state': {
            'label': 'Governance Eligible' if eligible_count else 'Blocked',
            'tone': 'normal' if eligible_count else 'warning',
            'icon': 'scale' if eligible_count else 'shield-alert',
            'description': (
                'Registry providers with committed inventory are eligible for governance refresh.'
                if eligible_count
                else 'Committed Registry inventory is required before governance synchronization.'
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
                'An Artifact Registry governance job is active.'
                if active_job
                else (
                    'Registry governance collection is ready.'
                    if eligible_count
                    else 'Synchronize Registry inventory before collecting governance evidence.'
                )
            ),
        },
    }
