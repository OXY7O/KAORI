from __future__ import annotations

from typing import Any

from app.artifact_registry.security.sync_jobs import (
    NoEligibleRegistrySecurityTargets,
    build_registry_security_targets,
    enqueue_artifact_registry_security_sync,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_SECURITY_SYNC_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_artifact_registry_security_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    try:
        job, created = enqueue_artifact_registry_security_sync(
            requested_by_user_id=requested_by_user_id,
            trigger_type=trigger_type,
        )
    except NoEligibleRegistrySecurityTargets as exc:
        return RegisteredJobDispatchResult(status='blocked', message=str(exc))
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'A canonical Artifact Registry security synchronization was queued.'
            if created
            else 'The request joined the active Artifact Registry security synchronization.'
        ),
        job=job,
        created=created,
    )


def build_artifact_registry_security_context(policy: JobPolicy) -> dict[str, Any]:
    registered = IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry').count()
    eligible = build_registry_security_targets()
    eligible_count = len(eligible)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_security',
        JobExecution.operation == ARTIFACT_REGISTRY_SECURITY_SYNC_OPERATION,
    )
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent[0] if recent else None
    blocked = max(registered - eligible_count, 0)

    if active is not None:
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'Artifact security evidence collection is active.',
        }
        configuration_state = {'label': 'Execution Active', 'tone': 'pending', 'icon': 'loader-circle'}
    elif eligible_count:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Committed Registry inventory is ready for security evidence collection.',
        }
        configuration_state = {
            'label': 'Enabled' if policy.enabled else 'Manual Only',
            'tone': 'normal' if policy.enabled else 'unknown',
            'icon': 'circle-check' if policy.enabled else 'mouse-pointer-click',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'Committed Registry inventory is required before security evidence can be collected.',
        }
        configuration_state = {'label': 'Blocked', 'tone': 'warning', 'icon': 'shield-alert'}

    return {
        'registered_source_count': registered,
        'eligible_source_count': eligible_count,
        'eligible_target_count': eligible_count,
        'blocked_source_count': blocked,
        'eligible_targets': eligible,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active) if active is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
        'execution_state': execution_state,
        'configuration_state': configuration_state,
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled and eligible_count else ('Waiting For Inventory' if policy.enabled else 'Disabled'),
            'tone': 'normal' if policy.enabled and eligible_count else ('warning' if policy.enabled else 'disabled'),
            'icon': 'circle-check' if policy.enabled and eligible_count else ('triangle-alert' if policy.enabled else 'circle-pause'),
            'description': (
                'Automatic Registry security evidence synchronization is scheduled.'
                if policy.enabled and eligible_count
                else 'Security collection waits for validated providers and committed Registry inventory.'
            ),
        },
        'readiness_state': {
            'label': 'Sync Eligible' if eligible_count else 'Blocked',
            'tone': 'normal' if eligible_count else 'warning',
            'icon': 'shield-check' if eligible_count else 'shield-alert',
            'description': (
                'Qualified Registry sources have committed inventory available.'
                if eligible_count
                else 'Run Artifact Registry Inventory Sync before security evidence collection.'
            ),
        },
        'diagnostics': (
            [] if eligible_count else ['No validated Registry source with committed inventory is eligible.']
        ),
    }
