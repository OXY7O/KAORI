from __future__ import annotations

from typing import Any

from app.artifact_registry.inventory.sync_jobs import (
    NoEligibleRegistryTargets,
    build_registry_inventory_targets,
    enqueue_artifact_registry_inventory_sync,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.policies.presentation import present_interval


def dispatch_artifact_registry_inventory_sync(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    try:
        job, created = enqueue_artifact_registry_inventory_sync(
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


def build_artifact_registry_inventory_context(policy: JobPolicy) -> dict[str, Any]:
    registered = IntegrationInstance.query.filter(IntegrationInstance.integration_type == 'registry').count()
    eligible = build_registry_inventory_targets()
    eligible_count = len(eligible)
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_inventory',
        JobExecution.operation == ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION,
    )
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent[0] if recent else None

    if active is not None:
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'An Artifact Registry inventory synchronization is active.',
        }
        configuration_state = {'label': 'Execution Active', 'tone': 'pending', 'icon': 'loader-circle'}
    elif eligible_count:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Qualified Registry providers are ready for committed inventory synchronization.',
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
            'description': 'No qualified Registry provider is ready for inventory synchronization.',
        }
        configuration_state = {'label': 'Blocked', 'tone': 'warning', 'icon': 'shield-alert'}

    scheduler_state = {
        'label': 'Enabled' if policy.enabled and eligible_count else ('Waiting For Ready Provider' if policy.enabled else 'Disabled'),
        'tone': 'normal' if policy.enabled and eligible_count else ('warning' if policy.enabled else 'disabled'),
        'icon': 'circle-check' if policy.enabled and eligible_count else ('triangle-alert' if policy.enabled else 'circle-pause'),
        'description': (
            'Automatic Artifact Registry inventory synchronization is scheduled.'
            if policy.enabled and eligible_count
            else (
                'Automatic synchronization is enabled, but no qualified Registry source is ready.'
                if policy.enabled
                else 'Automatic Artifact Registry inventory synchronization is disabled.'
            )
        ),
    }
    readiness_state = {
        'label': 'Sync Eligible' if eligible_count else 'Blocked',
        'tone': 'normal' if eligible_count else 'warning',
        'icon': 'link-2' if eligible_count else 'shield-alert',
        'description': (
            'Validated Registry providers are eligible for committed inventory synchronization.'
            if eligible_count
            else 'Register and validate a supported Registry provider before synchronizing.'
        ),
    }
    diagnostics = (
        []
        if eligible_count
        else ['No enabled Ready/Degraded Registry integration has a qualified inventory collector.']
    )
    return {
        'registered_source_count': registered,
        'eligible_source_count': eligible_count,
        'eligible_target_count': eligible_count,
        'blocked_source_count': max(registered - eligible_count, 0),
        'eligible_targets': eligible,
        'scheduler_state': scheduler_state,
        'readiness_state': readiness_state,
        'configuration_state': configuration_state,
        'execution_state': execution_state,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active) if active is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'recent_jobs': [present_job_execution(job) for job in recent],
        'diagnostics': diagnostics,
    }
