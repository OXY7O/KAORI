from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import current_app

from app.common.analytics.metrics import MetricsSourceError
from app.common.job_execution_contract import (
    OBJECT_STORAGE_ANALYTICS_MATERIALIZE_OPERATION,
    OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
)
from app.common.job_execution_presentation import present_job_execution
from app.models.job import JobExecution, JobPolicy
from app.models.object_storage import ObjectStorageSystem
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES, WORKLOAD_ANALYTICS, WORKLOAD_FORECASTING
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import enqueue_canonical_job
from app.platform_operations.jobs.policies.presentation import present_interval
from app.storage.object_storage.analytics.materialization import (
    analytics_snapshot_due,
    analytics_snapshot_state,
    forecast_snapshot_due,
    forecast_snapshot_state,
    get_analytics_snapshot,
    get_forecast_snapshot,
    required_contract_diagnostic,
    required_contract_ready,
)
from app.storage.object_storage.analytics.sources import resolve_object_storage_metrics_source
from app.storage.object_storage.analytics.tasks import (
    materialize_object_storage_analytics,
    materialize_object_storage_forecasts,
)


def _configured_windows(policy: JobPolicy) -> list[str]:
    configuration = policy.configuration_json or {}
    windows = [str(value) for value in configuration.get('history_windows') or ['7d', '30d', '90d']]
    return list(dict.fromkeys(value for value in windows if value in {'7d', '30d', '90d'})) or ['30d']


def _configured_time_ranges(policy: JobPolicy) -> list[str]:
    configuration = policy.configuration_json or {}
    allowed = {'1h', '6h', '12h', '24h', '7d', '30d', '60d'}
    ranges = [str(value) for value in configuration.get('time_ranges') or ['24h', '7d', '30d', '60d']]
    normalized = list(dict.fromkeys(value for value in ranges if value in allowed))
    if '24h' not in normalized:
        normalized.insert(0, '24h')
    return normalized or ['24h']


def _eligible_systems() -> tuple[list[ObjectStorageSystem], list[str]]:
    eligible: list[ObjectStorageSystem] = []
    diagnostics: list[str] = []
    for system in ObjectStorageSystem.query.order_by(ObjectStorageSystem.name.asc()).all():
        try:
            source = resolve_object_storage_metrics_source(system, execution_mode='background')
        except MetricsSourceError as exc:
            diagnostics.append(f'{system.name}: {exc}')
            continue
        if not required_contract_ready(source):
            diagnostics.append(f'{system.name}: {required_contract_diagnostic(source)}')
            continue
        eligible.append(system)
    return eligible, diagnostics


def _work_items(
    policy: JobPolicy,
    *,
    only_due: bool,
    requested_system_id: str | None = None,
    requested_history_window: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    eligible, diagnostics = _eligible_systems()
    if requested_system_id:
        eligible = [system for system in eligible if str(system.id) == requested_system_id]
    configuration = policy.configuration_json or {}
    freshness_minutes = int(configuration.get('freshness_minutes') or 120)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 4320)
    windows = _configured_windows(policy)
    if requested_history_window:
        windows = [requested_history_window] if requested_history_window in {'7d', '30d', '90d'} else []
    items: list[dict[str, Any]] = []
    for system in eligible:
        for history_window in windows:
            if only_due and not forecast_snapshot_due(system_id=system.id, history_window=history_window):
                continue
            items.append(
                {
                    'system_id': str(system.id),
                    'system_name': system.name,
                    'history_window': history_window,
                    'freshness_minutes': freshness_minutes,
                    'stale_grace_minutes': stale_grace_minutes,
                }
            )
    return items, diagnostics


def _analytics_work_items(
    policy: JobPolicy,
    *,
    only_due: bool,
    requested_system_id: str | None = None,
    requested_time_range: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    eligible, diagnostics = _eligible_systems()
    eligible = [system for system in eligible if system.inventory_observed_at is not None]
    if requested_system_id:
        eligible = [system for system in eligible if str(system.id) == requested_system_id]
    configuration = policy.configuration_json or {}
    freshness_minutes = int(configuration.get('freshness_minutes') or 15)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 1440)
    time_ranges = _configured_time_ranges(policy)
    if requested_time_range:
        time_ranges = (
            [requested_time_range] if requested_time_range in {'1h', '6h', '12h', '24h', '7d', '30d', '60d'} else []
        )
    items: list[dict[str, Any]] = []
    for system in eligible:
        for time_range in time_ranges:
            if only_due and not analytics_snapshot_due(system_id=system.id, time_range=time_range):
                continue
            items.append(
                {
                    'system_id': str(system.id),
                    'system_name': system.name,
                    'time_range': time_range,
                    'freshness_minutes': freshness_minutes,
                    'stale_grace_minutes': stale_grace_minutes,
                }
            )
    return items, diagnostics


def dispatch_object_storage_analytics_materialization(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    from app.platform_operations.jobs.policies.service import get_or_create_job_policy

    policy = get_or_create_job_policy('object_storage.analytics.materialize')
    parameters = parameters or {}
    items, diagnostics = _analytics_work_items(
        policy,
        only_due=trigger_type == 'scheduled',
        requested_system_id=str(parameters.get('system_id') or '') or None,
        requested_time_range=str(parameters.get('time_range') or '') or None,
    )
    if not items:
        if trigger_type == 'scheduled' and not diagnostics:
            return RegisteredJobDispatchResult(
                status='current',
                message='All configured Object Storage analytics snapshots are still current.',
            )
        detail = f' {" | ".join(diagnostics[:3])}' if diagnostics else ''
        return RegisteredJobDispatchResult(
            status='blocked',
            message=f'No Object Storage analytics work item is eligible.{detail}',
        )

    scope_key = str(parameters.get('system_id') or 'all')
    queue_name = current_app.config['ANALYTICS_CELERY_QUEUE']
    job, created = enqueue_canonical_job(
        task=materialize_object_storage_analytics,
        task_kwargs={'work_items': items},
        job_type='object_storage_analytics_materialization',
        operation=OBJECT_STORAGE_ANALYTICS_MATERIALIZE_OPERATION,
        queue_name=queue_name,
        workload_class=WORKLOAD_ANALYTICS,
        requested_by_user_id=requested_by_user_id,
        resource_group=f'object-storage-analytics:{scope_key}',
        parameters={'scope': scope_key, 'request': parameters},
        payload={
            'trigger_type': trigger_type,
            'work_item_count': len(items),
            'work_items': items,
        },
        scope_type='object_storage_analytics_fleet',
        scope_key=scope_key,
        max_attempts=2,
        soft_time_limit_seconds=current_app.config['ANALYTICS_TASK_SOFT_TIME_LIMIT_SECONDS'],
        hard_time_limit_seconds=current_app.config['ANALYTICS_TASK_HARD_TIME_LIMIT_SECONDS'],
        require_registered_worker=True,
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'active',
        message=(
            f'{len(items)} Object Storage analytics snapshot request(s) were queued.'
            if created
            else 'An equivalent Object Storage analytics materialization is already active.'
        ),
        job=job,
        created=created,
    )


def build_object_storage_analytics_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    eligible, diagnostics = _eligible_systems()
    eligible = [system for system in eligible if system.inventory_observed_at is not None]
    time_ranges = _configured_time_ranges(policy)
    states: list[dict[str, Any]] = []
    for system in eligible:
        for time_range in time_ranges:
            snapshot = get_analytics_snapshot(system_id=system.id, time_range=time_range)
            state = analytics_snapshot_state(snapshot)
            states.append({'system': system, 'time_range': time_range, **state})

    jobs_query = JobExecution.query.filter(
        JobExecution.job_type == 'object_storage_analytics_materialization',
        JobExecution.operation == OBJECT_STORAGE_ANALYTICS_MATERIALIZE_OPERATION,
    )
    active_job = (
        jobs_query.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    current_count = sum(row['label'] == 'Current' for row in states)
    stale_count = sum(str(row['label']).startswith('Stale') for row in states)
    failed_count = sum(row['label'] in {'Worker Failed', 'Expired', 'Snapshot Contract Invalid'} for row in states)
    attention_count = len(states) - current_count
    if active_job is not None:
        execution_state = {
            'label': 'Analytics Worker Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'The analytics-batch queue is refreshing Object Storage operational snapshots.',
        }
    elif eligible:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Eligible Object Storage systems are ready for analytics snapshot refresh.',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': diagnostics[0]
            if diagnostics
            else 'No inventory-ready Object Storage metrics binding is eligible.',
        }
    return {
        'eligible_system_count': len(eligible),
        'eligible_target_count': len(eligible),
        'materialization_target_label': 'Eligible Systems',
        'materialization_target_helper': 'Inventory + validated metrics binding',
        'materialization_dataset_label': 'Time Ranges',
        'materialization_dataset_helper': 'Precomputed analytics windows',
        'materialization_snapshot_helper': f'{attention_count} need refresh',
        'dataset_count': len(time_ranges),
        'time_ranges': time_ranges,
        'snapshot_count': len(states),
        'current_snapshot_count': current_count,
        'attention_snapshot_count': attention_count,
        'snapshot_health': {
            'current': current_count,
            'stale': stale_count,
            'failed': failed_count,
        },
        'queue_name': current_app.config['ANALYTICS_CELERY_QUEUE'],
        'diagnostics': diagnostics,
        'execution_state': execution_state,
        'configuration_state': execution_state,
        'readiness_state': execution_state,
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': (
                'Automatic Object Storage analytics refresh is scheduled.'
                if policy.enabled
                else 'Automatic Object Storage analytics refresh is disabled.'
            ),
        },
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(recent_jobs[0]) if recent_jobs else None,
        'recent_jobs': [present_job_execution(job) for job in recent_jobs],
        'refreshed_at': datetime.now(UTC),
    }


def dispatch_object_storage_forecast_materialization(
    *,
    requested_by_user_id: int | None,
    trigger_type: str,
    parameters: dict[str, Any] | None = None,
) -> RegisteredJobDispatchResult:
    from app.platform_operations.jobs.policies.service import get_or_create_job_policy

    policy = get_or_create_job_policy('object_storage.forecast.materialize')
    parameters = parameters or {}
    items, diagnostics = _work_items(
        policy,
        only_due=trigger_type == 'scheduled',
        requested_system_id=str(parameters.get('system_id') or '') or None,
        requested_history_window=str(parameters.get('history_window') or '') or None,
    )
    if not items:
        if trigger_type == 'scheduled' and not diagnostics:
            return RegisteredJobDispatchResult(
                status='current',
                message='All configured Object Storage forecast snapshots are still current.',
            )
        detail = f' {" | ".join(diagnostics[:3])}' if diagnostics else ''
        return RegisteredJobDispatchResult(
            status='blocked',
            message=f'No Object Storage forecast work item is eligible.{detail}',
        )

    scope_key = str(parameters.get('system_id') or 'all')
    queue_name = current_app.config['FORECASTING_CELERY_QUEUE']
    job, created = enqueue_canonical_job(
        task=materialize_object_storage_forecasts,
        task_kwargs={'work_items': items},
        job_type='object_storage_forecast_materialization',
        operation=OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
        queue_name=queue_name,
        workload_class=WORKLOAD_FORECASTING,
        requested_by_user_id=requested_by_user_id,
        resource_group=f'object-storage-forecast:{scope_key}',
        parameters={'scope': scope_key, 'request': parameters},
        payload={
            'trigger_type': trigger_type,
            'work_item_count': len(items),
            'work_items': items,
        },
        scope_type='object_storage_forecast_fleet',
        scope_key=scope_key,
        max_attempts=2,
        soft_time_limit_seconds=current_app.config['FORECASTING_TASK_SOFT_TIME_LIMIT_SECONDS'],
        hard_time_limit_seconds=current_app.config['FORECASTING_TASK_HARD_TIME_LIMIT_SECONDS'],
        require_registered_worker=True,
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'active',
        message=(
            f'{len(items)} Object Storage forecast snapshot request(s) were queued.'
            if created
            else 'An equivalent Object Storage forecast materialization is already active.'
        ),
        job=job,
        created=created,
    )


def build_object_storage_forecast_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    eligible, diagnostics = _eligible_systems()
    windows = _configured_windows(policy)
    states: list[dict[str, Any]] = []
    for system in eligible:
        for history_window in windows:
            snapshot = get_forecast_snapshot(system_id=system.id, history_window=history_window)
            state = forecast_snapshot_state(snapshot)
            states.append({'system': system, 'history_window': history_window, **state})

    jobs_query = JobExecution.query.filter(
        JobExecution.job_type == 'object_storage_forecast_materialization',
        JobExecution.operation == OBJECT_STORAGE_FORECAST_MATERIALIZE_OPERATION,
    )
    active_job = (
        jobs_query.filter(
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
            JobExecution.completed_at.is_(None),
        )
        .order_by(JobExecution.updated_at.desc(), JobExecution.id.desc())
        .first()
    )
    recent_jobs = jobs_query.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    current_count = sum(row['label'] == 'Current' for row in states)
    stale_count = sum(str(row['label']).startswith('Stale') for row in states)
    failed_count = sum(row['label'] in {'Worker Failed', 'Expired'} for row in states)
    attention_count = len(states) - current_count
    if active_job is not None:
        execution_state = {
            'label': 'Forecast Worker Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'The forecasting queue is refreshing Object Storage forecast snapshots.',
        }
    elif eligible:
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Eligible Object Storage systems are ready for forecast refresh.',
        }
    else:
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': diagnostics[0]
            if diagnostics
            else 'No eligible Object Storage metrics binding is available.',
        }
    return {
        'eligible_system_count': len(eligible),
        'eligible_target_count': len(eligible),
        'materialization_target_label': 'Eligible Systems',
        'materialization_target_helper': 'Validated metrics bindings',
        'materialization_dataset_label': 'History Windows',
        'materialization_dataset_helper': 'Forecast history scopes',
        'materialization_snapshot_helper': f'{attention_count} need refresh',
        'dataset_count': len(windows),
        'history_windows': windows,
        'snapshot_count': len(states),
        'current_snapshot_count': current_count,
        'attention_snapshot_count': attention_count,
        'snapshot_health': {
            'current': current_count,
            'stale': stale_count,
            'failed': failed_count,
        },
        'queue_name': current_app.config['FORECASTING_CELERY_QUEUE'],
        'diagnostics': diagnostics,
        'execution_state': execution_state,
        'configuration_state': execution_state,
        'readiness_state': execution_state,
        'scheduler_state': {
            'label': 'Enabled' if policy.enabled else 'Disabled',
            'tone': 'normal' if policy.enabled else 'disabled',
            'icon': 'circle-check' if policy.enabled else 'circle-pause',
            'description': (
                'Automatic Object Storage forecast refresh is scheduled.'
                if policy.enabled
                else 'Automatic Object Storage forecast refresh is disabled.'
            ),
        },
        'interval_label': present_interval(policy.interval_minutes),
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(recent_jobs[0]) if recent_jobs else None,
        'recent_jobs': [present_job_execution(job) for job in recent_jobs],
        'refreshed_at': datetime.now(UTC),
    }
