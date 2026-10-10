from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from app.common.job_execution_contract import ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.models.registry import RegistryAnalyticsSnapshot
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
        )
        .order_by(IntegrationInstance.id.asc())
        .all()
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
            require_registered_worker=True,
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


ANALYTICS_JOB_KEY = 'artifact_registry.analytics.materialize'
ANALYTICS_JOB_TYPE = 'artifact_registry_analytics'
_SUCCESS_STATUSES = ('succeeded', 'partially_succeeded')


def get_registry_analytics_job(public_id: str) -> JobExecution | None:
    return (
        JobExecution.query.filter(
            JobExecution.job_type == ANALYTICS_JOB_TYPE,
            JobExecution.operation == ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION,
            JobExecution.public_id == public_id,
        )
        .order_by(JobExecution.id.desc())
        .first()
    )


def _analytics_snapshot_posture(
    *,
    eligible_count: int,
    covered_count: int,
    current_count: int,
) -> tuple[str, str, str]:
    """Classify committed data without claiming worker/provider readiness from missing evidence."""
    if not eligible_count:
        return 'Blocked', 'warning', 'No eligible Registry providers. Validate and enable a provider first.'
    if not covered_count:
        return 'Not Materialized', 'warning', 'Collect analytics data to create committed Registry snapshots.'
    if current_count == eligible_count:
        return 'Current Snapshot', 'normal', 'All eligible providers have current committed analytics evidence.'
    if current_count:
        return 'Partial Coverage', 'warning', 'Some providers have stale or missing committed analytics snapshots.'
    return 'Stale Snapshot', 'warning', 'All available snapshots have expired; prior evidence remains readable.'


def build_registry_analytics_readiness() -> dict[str, Any]:
    """Read-only UI projection of canonical JobExecution and committed snapshots."""
    eligible_ids = _eligible_ids()
    registered_count = IntegrationInstance.query.filter_by(integration_type='registry').count()
    policy = JobPolicy.query.filter_by(job_key=ANALYTICS_JOB_KEY).first()
    jobs = JobExecution.query.filter(
        JobExecution.job_type == ANALYTICS_JOB_TYPE,
        JobExecution.operation == ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION,
    )
    active = (
        jobs.filter(JobExecution.status.in_(ACTIVE_JOB_STATUSES), JobExecution.completed_at.is_(None))
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    latest = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()
    success = (
        jobs.filter(JobExecution.status.in_(_SUCCESS_STATUSES))
        .order_by(JobExecution.completed_at.desc(), JobExecution.id.desc())
        .first()
    )

    snapshots: list[RegistryAnalyticsSnapshot] = []
    if eligible_ids:
        latest_ids = (
            RegistryAnalyticsSnapshot.query.with_entities(func.max(RegistryAnalyticsSnapshot.id))
            .filter(
                RegistryAnalyticsSnapshot.status == 'ready',
                RegistryAnalyticsSnapshot.integration_instance_id.in_(eligible_ids),
            )
            .group_by(RegistryAnalyticsSnapshot.integration_instance_id)
            .all()
        )
        ids = [int(row[0]) for row in latest_ids]
        if ids:
            snapshots = RegistryAnalyticsSnapshot.query.filter(RegistryAnalyticsSnapshot.id.in_(ids)).all()

    now = datetime.now(UTC)
    current = [
        item for item in snapshots
        if item.expires_at is None
        or (item.expires_at.replace(tzinfo=UTC) if item.expires_at.tzinfo is None else item.expires_at) > now
    ]
    label, tone, helper = _analytics_snapshot_posture(
        eligible_count=len(eligible_ids),
        covered_count=len(snapshots),
        current_count=len(current),
    )
    if active is not None:
        execution_label = 'Queued' if active.status == 'queued' else 'Collecting'
        execution_tone = 'pending'
        execution_helper = active.progress_message or 'Analytics materialization is running on the worker.'
    elif latest is not None and latest.status in {'failed', 'canceled', 'expired'}:
        execution_label, execution_tone = 'Last Attempt Failed', 'critical'
        execution_helper = 'The previous committed snapshots remain available; review the JobExecution failure.'
    elif success is not None:
        execution_label, execution_tone = 'Last Collection Completed', 'normal'
        execution_helper = 'New analytical evidence becomes available after the worker commits its snapshots.'
    else:
        execution_label, execution_tone = 'Not Collected', 'warning'
        execution_helper = 'Collect Registry analytics using the registered analytics worker.'

    latest_snapshot = max(snapshots, key=lambda item: item.generated_at) if snapshots else None
    return {
        'label': label,
        'tone': tone,
        'helper': helper,
        'execution_label': execution_label,
        'execution_tone': execution_tone,
        'execution_helper': execution_helper,
        'eligible_count': len(eligible_ids),
        'registered_count': registered_count,
        'covered_count': len(snapshots),
        'current_count': len(current),
        'snapshot_count': len(snapshots),
        'latest_generated_at': latest_snapshot.generated_at if latest_snapshot else None,
        'latest_expiry_at': latest_snapshot.expires_at if latest_snapshot else None,
        'is_active': active is not None,
        'active_job_public_id': active.public_id if active is not None else None,
        'active_job': present_job_execution(active) if active is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'last_success_label': present_user_datetime(
            success.completed_at if success else None, empty='Never'
        ),
        'last_attempt_label': present_user_datetime(
            latest.created_at if latest else None, empty='Never'
        ),
        'automatic_label': 'Enabled' if policy and policy.enabled else (
            'Manual Only' if policy else 'Not Configured'
        ),
        'interval_label': present_interval(policy.interval_minutes) if policy else 'Not Configured',
        'next_run_label': present_user_datetime(
            policy.next_run_at if policy else None, empty='Not Scheduled'
        ),
        'can_collect': bool(eligible_ids) and active is None,
    }
