from __future__ import annotations

from typing import Any

from app.common.job_execution_contract import ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_ANALYTICS
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.platform_operations.jobs.policies.presentation import present_interval


def _eligible_ids() -> list[int]:
    return [
        int(row.id)
        for row in IntegrationInstance.query.filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationInstance.readiness_status == 'ready',
        ).order_by(IntegrationInstance.id.asc()).all()
    ]


def dispatch_registry_analytics_materialization(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    del parameters
    from app.artifact_registry.analytics_tasks import materialize_registry_analytics_task

    ids = _eligible_ids()
    if not ids:
        return RegisteredJobDispatchResult(
            status='blocked',
            message='No Ready Registry provider is eligible for analytics materialization.',
        )
    job, created = enqueue_canonical_job(
        task=materialize_registry_analytics_task,
        task_kwargs={
            'integration_instance_ids': ids,
            'requested_by_user_id': requested_by_user_id,
        },
        job_type='artifact_registry_analytics',
        operation=ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION,
        queue_name='analytics-batch',
        workload_class=WORKLOAD_ANALYTICS,
        requested_by_user_id=requested_by_user_id,
        integration_type='registry',
        integration_instance_id=None,
        scope_type='registry_analytics_fleet',
        scope_key='all',
        resource_group='artifact-registry-analytics:global',
        parameters={'scope': 'all'},
        payload={'total_count': len(ids), 'targets': ids, 'trigger_type': trigger_type},
        max_attempts=3,
        dispatch_options=JobDispatchOptions(
            soft_time_limit_seconds=600,
            hard_time_limit_seconds=900,
        ),
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'Artifact Registry analytics materialization was queued.'
            if created
            else 'The request joined the active Artifact Registry analytics materialization.'
        ),
        job=job,
        created=created,
    )


def build_registry_analytics_context(policy: JobPolicy) -> dict[str, Any]:
    eligible_ids = _eligible_ids()
    registered_count = IntegrationInstance.query.filter_by(integration_type='registry').count()
    jobs = JobExecution.query.filter(
        JobExecution.job_type == 'artifact_registry_analytics',
        JobExecution.operation == ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION,
    )
    active_job = (
        jobs.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent[0] if recent else None
    return {
        'registered_system_count': registered_count,
        'eligible_system_count': len(eligible_ids),
        'eligible_target_count': len(eligible_ids),
        'blocked_system_count': max(registered_count - len(eligible_ids), 0),
        'eligible_targets': eligible_ids,
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active_job) if active_job else None,
        'latest_job': present_job_execution(latest) if latest else None,
        'recent_jobs': [present_job_execution(row) for row in recent],
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': 'Automatic Registry analytics materialization policy.',
        },
        'readiness_state': {
            'label': 'Ready' if eligible_ids else 'Blocked',
            'tone': 'normal' if eligible_ids else 'warning',
            'icon': 'chart-column' if eligible_ids else 'shield-alert',
            'description': 'Analytics consumes committed Registry evidence and optional bound Metrics Source queries.',
        },
        'configuration_state': {
            'label': 'Execution Active' if active_job else ('Enabled' if policy.enabled else 'Manual Only'),
            'tone': 'pending' if active_job else ('normal' if policy.enabled else 'unknown'),
            'icon': 'loader-circle' if active_job else ('circle-check' if policy.enabled else 'mouse-pointer-click'),
        },
        'execution_state': {
            'label': 'Execution Active' if active_job else ('Ready' if eligible_ids else 'Blocked'),
            'tone': 'pending' if active_job else ('normal' if eligible_ids else 'warning'),
            'icon': 'loader-circle' if active_job else ('circle-check' if eligible_ids else 'shield-alert'),
            'description': 'Current analytics worker execution posture.',
        },
    }
