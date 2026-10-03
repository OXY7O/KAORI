from __future__ import annotations

from typing import Any

from app.artifact_registry.inventory.sync_jobs import (
    NoEligibleRegistryTargets,
    build_registry_inventory_targets,
    enqueue_artifact_registry_inventory_sync,
)
from app.common.job_execution_contract import ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION
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
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_inventory',
        JobExecution.operation == ARTIFACT_REGISTRY_INVENTORY_SYNC_OPERATION,
    )
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc())
        .first()
    )
    return {
        'registered_source_count': registered,
        'eligible_source_count': len(eligible),
        'eligible_targets': eligible,
        'active_job': active,
        'interval_label': present_interval(policy.interval_minutes),
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled and eligible else ('warning' if policy.enabled else 'disabled'),
            'icon': 'circle-check' if policy.enabled and eligible else 'triangle-alert',
            'description': (
                'Automatic Artifact Registry inventory synchronization is scheduled.'
                if policy.enabled and eligible
                else 'No qualified Registry source is currently eligible for synchronization.'
            ),
        },
        'readiness_state': {
            'label': 'Sync Eligible' if eligible else 'Blocked',
            'tone': 'normal' if eligible else 'warning',
            'icon': 'link-2' if eligible else 'shield-alert',
            'description': (
                'Validated Registry providers are eligible for committed inventory sync.'
                if eligible
                else 'Register and validate a Registry provider before syncing.'
            ),
        },
    }
