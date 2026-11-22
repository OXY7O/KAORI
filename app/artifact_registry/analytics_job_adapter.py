from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func

from app.common.job_execution_contract import ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION
from app.common.job_execution_presentation import present_job_execution
from app.common.presentation import present_user_datetime
from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution, JobPolicy
from app.models.registry import RegistryAnalyticsSnapshot
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_ANALYTICS
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.platform_operations.jobs.policies.presentation import present_interval


def rollback_registry_analytics_materialization_dispatch() -> None:
    """Reset a failed Registry analytics job-dispatch transaction before feedback."""
    db.session.rollback()


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
    from app.artifact_registry.analytics_tasks import materialize_registry_analytics_task

    time_range = str((parameters or {}).get('snapshot_window') or 'current')
    if time_range not in _ANALYTICS_SNAPSHOT_WINDOWS:
        raise ValueError('Unsupported Registry Analytics history window.')

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
            'time_range': time_range,
        },
        job_type='artifact_registry_analytics',
        operation=ARTIFACT_REGISTRY_ANALYTICS_MATERIALIZE_OPERATION,
        queue_name='analytics-batch',
        workload_class=WORKLOAD_ANALYTICS,
        requested_by_user_id=requested_by_user_id,
        integration_type='registry',
        integration_instance_id=None,
        scope_type='registry_analytics_fleet',
        scope_key=f'all:{time_range}',
        resource_group=f'artifact-registry-analytics:{time_range}',
        parameters={'scope': 'all', 'snapshot_window': time_range},
        payload={
            'total_count': len(ids),
            'targets': ids,
            'trigger_type': trigger_type,
            'time_range': time_range,
        },
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


# Registry time ranges filter committed snapshot age, not provider telemetry history.
_ANALYTICS_SNAPSHOT_WINDOWS = {
    '1h': timedelta(hours=1),
    '6h': timedelta(hours=6),
    '12h': timedelta(hours=12),
    '24h': timedelta(hours=24),
    '7d': timedelta(days=7),
    '30d': timedelta(days=30),
    '60d': timedelta(days=60),
    'current': None,  # Explicit legacy/all-age latest snapshot mode.
}


def normalize_registry_analytics_window(window: str) -> str:
    return window if window in _ANALYTICS_SNAPSHOT_WINDOWS else '24h'


def analytics_snapshot_matches_window(
    snapshot: RegistryAnalyticsSnapshot,
    window: str,
    *,
    now: datetime | None = None,
) -> bool:
    """A worker dataset's range must match the requested measured interval."""
    del now
    return snapshot.time_range == normalize_registry_analytics_window(window)


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
    snapshot_views: list[dict[str, Any]] | None = None,
) -> tuple[str, str, str]:
    """Classify selected-window committed evidence without assuming all non-current data expired."""
    if not eligible_count:
        return 'Blocked', 'warning', 'No eligible Registry providers. Validate and enable a provider first.'
    if not covered_count:
        return (
            'Not Materialized',
            'warning',
            'The registered analytics worker has not yet committed Registry snapshots.',
        )
    if current_count == eligible_count:
        return 'Current Snapshot', 'normal', 'All eligible providers have current committed analytics evidence.'
    if current_count:
        return (
            'Partial Coverage',
            'warning',
            'Some sources are missing current evidence; check expiry, changed inputs, and source completeness.',
        )
    if covered_count < eligible_count:
        return (
            'Partial Coverage',
            'warning',
            'Some eligible sources have no selected-window snapshot; existing evidence is not current.',
        )

    views = snapshot_views or []
    if views and all(bool(view.get('is_stale')) for view in views):
        return (
            'Stale Snapshot',
            'warning',
            'Selected-window snapshots have expired; earlier committed evidence remains readable.',
        )
    if views and all(view.get('label') == 'Inputs Changed' and not view.get('is_stale') for view in views):
        return (
            'Inputs Changed',
            'warning',
            'Committed Registry inputs changed after this window was materialized; refresh the selected interval.',
        )
    if views and all(view.get('label') == 'Partial Evidence' for view in views):
        return (
            'Partial Evidence',
            'warning',
            'Committed snapshots exist, but required Metrics Source or governance evidence is incomplete.',
        )
    return (
        'Snapshot Attention',
        'warning',
        'Committed snapshots are not current; check expiry, changed inputs, and incomplete evidence.',
    )


def _registry_analytics_last_job_window(job: JobExecution | None) -> str | None:
    """Read a JobExecution's committed fleet scope without inferring the selected UI window."""
    scope_key = getattr(job, 'scope_key', None)
    if not isinstance(scope_key, str) or not scope_key.startswith('all:'):
        return None
    window = scope_key.partition(':')[2]
    return window if window in _ANALYTICS_SNAPSHOT_WINDOWS else None


_AUTO_RETRY_COOLDOWN = timedelta(minutes=5)


def should_request_registry_analytics_materialization(
    readiness: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Follow the K8s on-demand materialization model without a duplicate dispatch loop."""
    if (
        not readiness['eligible_count']
        or readiness['is_active']
        or readiness['current_count'] >= readiness['eligible_count']
    ):
        return False
    last_attempt = readiness.get('latest_attempt_at')
    if last_attempt is not None:
        reference = last_attempt.replace(tzinfo=UTC) if last_attempt.tzinfo is None else last_attempt
        if (now or datetime.now(UTC)) - reference < _AUTO_RETRY_COOLDOWN:
            return False
    return True


def registry_analytics_dependency_steps(
    *,
    registered_count: int,
    eligible_count: int,
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Present three independent committed-evidence boundaries without probing providers.

    A missing worker snapshot says Not Collected, not Not Bound. This summary is
    limited to the already-selected Registry scope and time window.
    """
    if registered_count == 0:
        provider_status, provider_tone = 'Not Configured', 'unknown'
    elif eligible_count == registered_count:
        provider_status, provider_tone = 'Ready', 'normal'
    elif eligible_count:
        provider_status, provider_tone = 'Partial', 'warning'
    else:
        provider_status, provider_tone = 'Validation Required', 'warning'

    steps = [
        {
            'key': 'domain',
            'label': 'Registry Integration',
            'icon': 'package',
            'status': provider_status,
            'tone': provider_tone,
            'description': 'Provider/instance eligibility for committed Registry collection.',
            'detail': f'{eligible_count} / {registered_count} registered sources eligible.',
        }
    ]
    for key, label, icon, description in (
        (
            'metrics',
            'Metrics Source',
            'activity',
            'Committed operational telemetry; history requires a qualified range.',
        ),
        (
            'alerts',
            'Alert Source',
            'bell-ring',
            'Committed lifecycle alerts or qualified metrics-backed fallback.',
        ),
    ):
        ready = 0
        partial = 0
        current_ready = 0
        fallback = False
        for row in evidence:
            section = row.get(key)
            if not isinstance(section, dict):
                continue
            status = section.get('status')
            if status == 'ready':
                ready += 1
                current_ready += int(bool(row.get('current')))
                fallback = fallback or (key == 'alerts' and bool(section.get('fallback_used')))
            elif status == 'partial':
                partial += 1

        if not evidence:
            status_label, tone = 'Not Collected', 'unknown'
        elif eligible_count and current_ready == eligible_count:
            status_label = 'Fallback Evidence' if fallback else 'Evidence Ready'
            tone = 'warning' if fallback else 'normal'
        elif ready or partial:
            status_label, tone = 'Partial Evidence', 'warning'
        else:
            status_label, tone = 'Evidence Unavailable', 'unknown'
        steps.append(
            {
                'key': key,
                'label': label,
                'icon': icon,
                'status': status_label,
                'tone': tone,
                'description': description,
                'detail': (
                    f'{ready} / {eligible_count} sources with committed evidence. '
                    'This is snapshot coverage, not a live binding or provider health check.'
                ),
            }
        )
    return steps


def _registry_analytics_snapshot_source_evidence(
    snapshots: list[RegistryAnalyticsSnapshot],
    snapshot_views: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence = []
    for snapshot, view in zip(snapshots, snapshot_views, strict=True):
        payload = snapshot.payload_json if isinstance(snapshot.payload_json, dict) else {}
        evidence.append(
            {
                'metrics': payload.get('metrics'),
                'alerts': payload.get('alerts'),
                'current': bool(view['is_current']),
            }
        )
    return evidence

def build_registry_analytics_readiness(
    *,
    provider_id: int | None = None,
    snapshot_window: str = '24h',
) -> dict[str, Any]:
    """Read-only UI projection of canonical JobExecution and committed snapshots."""
    eligible_ids = _eligible_ids()
    if provider_id is not None:
        eligible_ids = [value for value in eligible_ids if value == provider_id]
    registered = IntegrationInstance.query.filter_by(integration_type='registry')
    registered_count = registered.filter_by(id=provider_id).count() if provider_id is not None else registered.count()
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
    normalized_window = normalize_registry_analytics_window(snapshot_window)
    if eligible_ids:
        latest_ids = (
            RegistryAnalyticsSnapshot.query.with_entities(func.max(RegistryAnalyticsSnapshot.id))
            .filter(
                RegistryAnalyticsSnapshot.status == 'ready',
                RegistryAnalyticsSnapshot.time_range == normalized_window,
                RegistryAnalyticsSnapshot.integration_instance_id.in_(eligible_ids),
            )
            .group_by(RegistryAnalyticsSnapshot.integration_instance_id)
            .all()
        )
        ids = [int(row[0]) for row in latest_ids]
        if ids:
            snapshots = RegistryAnalyticsSnapshot.query.filter(RegistryAnalyticsSnapshot.id.in_(ids)).all()
    has_older_evidence = bool(snapshots)

    from app.artifact_registry.presentation_common import _analytics_snapshot_view

    snapshot_views = [_analytics_snapshot_view(item) for item in snapshots]
    dependency_steps = registry_analytics_dependency_steps(
        registered_count=registered_count,
        eligible_count=len(eligible_ids),
        evidence=_registry_analytics_snapshot_source_evidence(snapshots, snapshot_views),
    )
    current_count = sum(bool(view['is_current']) for view in snapshot_views)
    label, tone, helper = _analytics_snapshot_posture(
        eligible_count=len(eligible_ids),
        covered_count=len(snapshots),
        current_count=current_count,
        snapshot_views=snapshot_views,
    )
    if normalized_window != 'current' and not has_older_evidence and eligible_ids:
        label, tone, helper = (
            'Historical Materialization Required',
            'warning',
            'No worker-materialized source range dataset is available for the requested interval.',
        )
    if active is not None:
        execution_label = 'Queued' if active.status == 'queued' else 'Collecting'
        execution_tone = 'pending'
        execution_helper = active.progress_message or 'Analytics materialization is running on the worker.'
    elif latest is not None and latest.status in {'failed', 'canceled', 'expired'}:
        execution_label, execution_tone = 'Last Attempt Failed', 'critical'
        execution_helper = 'The previous committed snapshots remain available; review the JobExecution failure.'
    elif latest is not None and latest.status == 'partially_succeeded':
        execution_label, execution_tone = 'Partial Evidence', 'warning'
        execution_helper = 'One or more Registry sources or optional Metrics Source datasets were unavailable.'
    elif success is not None:
        execution_label, execution_tone = 'Last Collection Completed', 'normal'
        execution_helper = 'New analytical evidence becomes available after the worker commits its snapshots.'
    else:
        execution_label, execution_tone = 'Not Collected', 'warning'
        execution_helper = 'Analytics data will be materialized by the registered worker when scheduled or requested.'

    latest_snapshot = max(snapshots, key=lambda item: item.generated_at) if snapshots else None
    last_attempt_window = _registry_analytics_last_job_window(latest)
    if latest is not None and latest.status in {'failed', 'canceled', 'expired'} and active is None:
        if label == 'Current Snapshot':
            label, tone = 'Refresh Failed', 'warning'
        helper = 'Latest Analytics refresh failed; prior committed snapshot validity is shown separately.'
    return {
        'label': label,
        'tone': tone,
        'helper': helper,
        'execution_label': execution_label,
        'execution_tone': execution_tone,
        'execution_helper': execution_helper,
        'dependency_steps': dependency_steps,
        'eligible_count': len(eligible_ids),
        'registered_count': registered_count,
        'covered_count': len(snapshots),
        'current_count': current_count,
        'snapshot_count': len(snapshots),
        'last_attempt_window': last_attempt_window,
        'latest_generated_at': latest_snapshot.generated_at if latest_snapshot else None,
        'latest_expiry_at': latest_snapshot.expires_at if latest_snapshot else None,
        'is_active': active is not None,
        'active_job_public_id': active.public_id if active is not None else None,
        'active_job': present_job_execution(active) if active is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'last_success_label': present_user_datetime(success.completed_at if success else None, empty='Never'),
        'last_attempt_label': present_user_datetime(latest.created_at if latest else None, empty='Never'),
        'automatic_label': 'Enabled' if policy and policy.enabled else ('Manual Only' if policy else 'Not Configured'),
        'interval_label': present_interval(policy.interval_minutes) if policy else 'Not Configured',
        'next_run_label': present_user_datetime(policy.next_run_at if policy else None, empty='Not Scheduled'),
        'latest_status': latest.status if latest else None,
        'latest_attempt_at': latest.created_at if latest else None,
        'collection_warning': None,
    }
