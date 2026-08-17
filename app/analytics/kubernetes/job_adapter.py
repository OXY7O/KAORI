from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app

from app.alertmanager.consumer import KUBERNETES_CLUSTER_SCOPE
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.analytics.kubernetes.materialization.catalog import (
    FORECAST_DATASET,
    canonical_parameters,
    dataset_range,
    dataset_task_budget_seconds,
    get_dataset,
    list_analytics_datasets,
    source_binding_capabilities,
    source_technical_capabilities,
)
from app.analytics.kubernetes.materialization.identity import normalize_parameters
from app.analytics.kubernetes.materialization.keys import CAPACITY_DATASET_KEY
from app.analytics.kubernetes.materialization.service import get_snapshot
from app.analytics.kubernetes.tasks import materialize_analytics_snapshots, materialize_forecast_snapshots
from app.common.job_execution_presentation import present_job_execution
from app.jobs.constants import ACTIVE_JOB_STATUSES
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.dispatcher import enqueue_canonical_job
from app.models import AnalyticsSnapshot, Cluster
from app.models.job import JobExecution, JobPolicy
from app.metrics.repository import resolve_instance_for_cluster
from app.metrics.resolver import resolve_metrics_sources

_DASHBOARD_REQUIRED_24H_DATASETS = {CAPACITY_DATASET_KEY}
_RANGE_ORDER = {
    '1h': 0,
    '6h': 1,
    '12h': 2,
    '24h': 3,
    '7d': 4,
    '30d': 5,
    '60d': 6,
    '90d': 7,
}
logger = logging.getLogger(__name__)


def _append_eligibility_diagnostic(
    diagnostics: list[str] | None,
    message: str,
) -> None:
    normalized = str(message or '').strip()
    if diagnostics is not None and normalized and normalized not in diagnostics:
        diagnostics.append(normalized[:1000])


def _registered_clusters() -> list[Cluster]:
    return Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()


def _metrics_source_eligible_clusters(clusters: list[Cluster] | None = None) -> list[Cluster]:
    candidates = clusters if clusters is not None else _registered_clusters()
    return [
        cluster
        for cluster in candidates
        if (instance := resolve_instance_for_cluster(cluster.id)) is not None and instance.endpoint.strip()
    ]


def _metrics_source_dataset_eligible(
    cluster: Cluster,
    dataset_key: str,
    diagnostics: list[str] | None = None,
) -> bool:
    try:
        resolution = resolve_metrics_sources(
            scope_type=KUBERNETES_CLUSTER_SCOPE,
            scope_key=str(cluster.id),
            required_binding_capabilities=source_binding_capabilities(dataset_key),
            required_technical_capabilities=source_technical_capabilities(dataset_key),
        )
    except Exception as exc:
        _append_eligibility_diagnostic(
            diagnostics,
            f'{dataset_key} on {cluster.name}: source resolution failed: {exc}',
        )
        logger.warning(
            'Could not evaluate Metrics Source eligibility for analytics dataset.',
            extra={
                'cluster_id': str(cluster.id),
                'dataset_key': dataset_key,
                'error': str(exc)[:1000],
            },
        )
        return False
    if resolution.selected is None:
        reason = (
            resolution.candidates[0].decision_reason
            if resolution.candidates
            else 'No bound Metrics Source source is available.'
        )
        _append_eligibility_diagnostic(
            diagnostics,
            f'{dataset_key} on {cluster.name}: {reason}',
        )
        return False
    return True


def _alert_dataset_eligible(
    cluster: Cluster,
    dataset_key: str,
    parameters: dict[str, Any] | None = None,
    diagnostics: list[str] | None = None,
) -> bool:
    source = canonical_parameters(dataset_key, parameters).get('source', 'auto').lower()
    if source in {'auto', 'alertmanager'}:
        try:
            alertmanager = resolve_alertmanager_sources(
                scope_type=KUBERNETES_CLUSTER_SCOPE,
                scope_key=str(cluster.id),
            )
        except Exception as exc:
            _append_eligibility_diagnostic(
                diagnostics,
                f'{dataset_key} on {cluster.name}: Alertmanager resolution failed: {exc}',
            )
            logger.warning(
                'Could not evaluate Alertmanager eligibility for analytics dataset.',
                extra={
                    'cluster_id': str(cluster.id),
                    'dataset_key': dataset_key,
                    'requested_source': source,
                    'error': str(exc)[:1000],
                },
            )
            alertmanager = None
        if alertmanager is not None and alertmanager.selected is not None:
            return True

    if source in {'auto', 'metrics_source'}:
        try:
            metrics_source = resolve_metrics_sources(
                scope_type=KUBERNETES_CLUSTER_SCOPE,
                scope_key=str(cluster.id),
                required_binding_capabilities=('metrics',),
                required_technical_capabilities=('instant_query',),
            )
        except Exception as exc:
            _append_eligibility_diagnostic(
                diagnostics,
                f'{dataset_key} on {cluster.name}: Metrics Source fallback resolution failed: {exc}',
            )
            logger.warning(
                'Could not evaluate Metrics Source fallback eligibility for alerts analytics.',
                extra={
                    'cluster_id': str(cluster.id),
                    'dataset_key': dataset_key,
                    'requested_source': source,
                    'error': str(exc)[:1000],
                },
            )
            metrics_source = None
        if metrics_source is not None and metrics_source.selected is not None:
            return True

    _append_eligibility_diagnostic(
        diagnostics,
        f'{dataset_key} on {cluster.name}: no eligible {source} alert source is available.',
    )
    return False


def _dataset_eligible(
    cluster: Cluster,
    dataset_key: str,
    parameters: dict[str, Any] | None = None,
    diagnostics: list[str] | None = None,
) -> bool:
    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'metrics_source':
        return _metrics_source_dataset_eligible(cluster, dataset_key, diagnostics)
    if dataset.source_kind == 'alert':
        return _alert_dataset_eligible(cluster, dataset_key, parameters, diagnostics)
    return True


def _analytics_eligible_clusters() -> tuple[list[Cluster], set[str]]:
    clusters = _registered_clusters()
    metrics_source_clusters = _metrics_source_eligible_clusters(clusters)
    metrics_source_ids = {str(cluster.id) for cluster in metrics_source_clusters}
    eligible = list(metrics_source_clusters)
    for cluster in clusters:
        cluster_id = str(cluster.id)
        if cluster_id in metrics_source_ids:
            continue
        if _alert_dataset_eligible(cluster, 'analytics.alerts', {'source': 'alertmanager'}):
            eligible.append(cluster)
    return eligible, metrics_source_ids


def _range_freshness_minutes(value: str | None, base_minutes: int) -> int:
    minimum_by_range = {
        '24h': 20,
        '7d': 60,
        '30d': 180,
        '60d': 360,
    }
    return max(base_minutes, minimum_by_range.get(value or '', base_minutes))


def _forecast_freshness_minutes(history_window: str, base_minutes: int) -> int:
    minimum_by_history = {'7d': 60, '30d': 120, '90d': 360}
    return max(base_minutes, minimum_by_history.get(history_window, base_minutes))


def _work_item_range(item: dict[str, Any]) -> str:
    parameters = item.get('parameters')
    return dataset_range(
        str(item['dataset_key']),
        parameters if isinstance(parameters, dict) else None,
    )


def _work_item_sort_key(item: dict[str, Any]) -> tuple[int, int, str, str]:
    dataset = get_dataset(str(item['dataset_key']))
    selected_range = _work_item_range(item)
    return (
        dataset.execution_priority,
        _RANGE_ORDER.get(selected_range, 0),
        str(item.get('cluster_id') or ''),
        dataset.key,
    )


def _work_item_budget_seconds(item: dict[str, Any]) -> int:
    parameters = item.get('parameters')
    return dataset_task_budget_seconds(
        str(item['dataset_key']),
        parameters if isinstance(parameters, dict) else None,
    )


def _effective_task_limits(
    work_items: list[dict[str, Any]],
    *,
    forecasting: bool,
) -> tuple[int, int, int]:
    soft_key = 'FORECASTING_TASK_SOFT_TIME_LIMIT_SECONDS' if forecasting else 'ANALYTICS_TASK_SOFT_TIME_LIMIT_SECONDS'
    hard_key = 'FORECASTING_TASK_HARD_TIME_LIMIT_SECONDS' if forecasting else 'ANALYTICS_TASK_HARD_TIME_LIMIT_SECONDS'
    max_key = (
        'FORECASTING_TASK_MAX_SOFT_TIME_LIMIT_SECONDS' if forecasting else 'ANALYTICS_TASK_MAX_SOFT_TIME_LIMIT_SECONDS'
    )
    base_soft = int(current_app.config[soft_key])
    base_hard = int(current_app.config[hard_key])
    maximum_soft = int(current_app.config.get(max_key, 14400 if forecasting else 7200))
    estimated_seconds = 120 + sum(_work_item_budget_seconds(item) for item in work_items)
    soft_limit = min(max(base_soft, estimated_seconds), maximum_soft)
    hard_limit = max(base_hard, soft_limit + 60)
    return soft_limit, hard_limit, estimated_seconds


def _snapshot_due(*, cluster_id: str, dataset_key: str, parameters: dict[str, Any]) -> bool:
    snapshot = get_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
    )
    if snapshot is None or snapshot.payload_json is None or snapshot.expires_at is None:
        return True
    expires_at = snapshot.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def _configured_values(policy: JobPolicy, key: str, defaults: list[str]) -> list[str]:
    configuration = policy.configuration_json or {}
    values = configuration.get(key)
    if not isinstance(values, list):
        return defaults
    normalized = [str(value).strip() for value in values if str(value).strip()]
    return normalized or defaults


def _analytics_work_items(
    policy: JobPolicy,
    parameters: dict[str, Any] | None,
    *,
    clusters: list[Cluster],
    only_due: bool,
    metrics_source_cluster_ids: set[str] | None = None,
    eligibility_diagnostics: list[str] | None = None,
) -> list[dict[str, Any]]:
    configuration = policy.configuration_json or {}
    if metrics_source_cluster_ids is None:
        metrics_source_cluster_ids = {str(cluster.id) for cluster in clusters}
    freshness_minutes = int(configuration.get('freshness_minutes') or 20)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 1440)
    if parameters and parameters.get('dataset_key') and parameters.get('cluster_id'):
        cluster_id = str(parameters['cluster_id'])
        dataset_key = str(parameters['dataset_key'])
        eligible_cluster_ids = {str(cluster.id) for cluster in clusters}
        if cluster_id not in eligible_cluster_ids:
            return []
        dataset = get_dataset(dataset_key)
        if dataset.source_kind == 'metrics_source' and cluster_id not in metrics_source_cluster_ids:
            return []
        cluster = next((item for item in clusters if str(item.id) == cluster_id), None)
        snapshot_parameters = canonical_parameters(
            dataset_key,
            parameters.get('snapshot_parameters'),
        )
        if cluster is None or not _dataset_eligible(
            cluster,
            dataset_key,
            snapshot_parameters,
            eligibility_diagnostics,
        ):
            return []
        selected_range = snapshot_parameters.get('time_range')
        if dataset.key == 'analytics.utilization.trend':
            selected_range = {
                '1': '1h',
                '6': '6h',
                '12': '12h',
                '24': '24h',
                '168': '7d',
                '720': '30d',
                '1440': '60d',
            }.get(snapshot_parameters.get('trend_hours', ''))
        return [
            {
                'cluster_id': cluster_id,
                'dataset_key': dataset_key,
                'parameters': snapshot_parameters,
                'freshness_minutes': _range_freshness_minutes(
                    selected_range,
                    max(freshness_minutes, dataset.freshness_minutes),
                ),
                'stale_grace_minutes': min(
                    stale_grace_minutes,
                    dataset.stale_grace_minutes,
                ),
            }
        ]
    ranges = _configured_values(policy, 'time_ranges', ['24h', '7d', '30d', '60d'])
    trend_range_by_hours = {
        '1': '1h',
        '6': '6h',
        '12': '12h',
        '24': '24h',
        '168': '7d',
        '720': '30d',
        '1440': '60d',
    }
    work_items: list[dict[str, Any]] = []
    for cluster in clusters:
        cluster_id = str(cluster.id)
        for dataset in list_analytics_datasets():
            if dataset.source_kind == 'metrics_source' and cluster_id not in metrics_source_cluster_ids:
                continue
            for default_parameters in dataset.default_parameters:
                if not _dataset_eligible(
                    cluster,
                    dataset.key,
                    default_parameters,
                    eligibility_diagnostics,
                ):
                    continue
                time_range = default_parameters.get('time_range')
                trend_range = trend_range_by_hours.get(str(default_parameters.get('trend_hours') or ''))
                selected_range = time_range or trend_range
                dashboard_required_range = dataset.key in _DASHBOARD_REQUIRED_24H_DATASETS and selected_range == '24h'
                if selected_range and selected_range not in ranges and not dashboard_required_range:
                    continue
                snapshot_parameters = canonical_parameters(
                    dataset.key,
                    {
                        'cluster_id': str(cluster.id),
                        **default_parameters,
                    },
                )
                item_freshness = _range_freshness_minutes(
                    selected_range,
                    max(freshness_minutes, dataset.freshness_minutes),
                )
                if only_due and not _snapshot_due(
                    cluster_id=cluster.id,
                    dataset_key=dataset.key,
                    parameters=snapshot_parameters,
                ):
                    continue
                work_items.append(
                    {
                        'cluster_id': cluster.id,
                        'dataset_key': dataset.key,
                        'parameters': snapshot_parameters,
                        'freshness_minutes': item_freshness,
                        'stale_grace_minutes': min(
                            stale_grace_minutes,
                            dataset.stale_grace_minutes,
                        ),
                    }
                )
    return work_items


def _forecast_work_items(
    policy: JobPolicy,
    parameters: dict[str, Any] | None,
    *,
    clusters: list[Cluster],
    only_due: bool,
    eligibility_diagnostics: list[str] | None = None,
) -> list[dict[str, Any]]:
    configuration = policy.configuration_json or {}
    freshness_minutes = int(configuration.get('freshness_minutes') or 120)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 4320)
    if parameters and parameters.get('dataset_key') and parameters.get('cluster_id'):
        cluster_id = str(parameters['cluster_id'])
        cluster = next((item for item in clusters if str(item.id) == cluster_id), None)
        if cluster is None or not _metrics_source_dataset_eligible(
            cluster,
            FORECAST_DATASET.key,
            eligibility_diagnostics,
        ):
            return []
        snapshot_parameters = canonical_parameters(
            FORECAST_DATASET.key,
            parameters.get('snapshot_parameters'),
        )
        history_window = snapshot_parameters.get('history_window', '30d')
        return [
            {
                'cluster_id': cluster_id,
                'dataset_key': FORECAST_DATASET.key,
                'parameters': snapshot_parameters,
                'freshness_minutes': _forecast_freshness_minutes(
                    history_window,
                    freshness_minutes,
                ),
                'stale_grace_minutes': min(
                    stale_grace_minutes,
                    FORECAST_DATASET.stale_grace_minutes,
                ),
            }
        ]
    configured_history = {
        value
        for value in _configured_values(
            policy,
            'history_windows',
            ['7d', '30d', '90d'],
        )
        if value in {'7d', '30d', '90d'}
    }
    configured_history.add('30d')
    history_windows = [value for value in ('7d', '30d', '90d') if value in configured_history]
    work_items: list[dict[str, Any]] = []
    for cluster in clusters:
        if not _metrics_source_dataset_eligible(
            cluster,
            FORECAST_DATASET.key,
            eligibility_diagnostics,
        ):
            continue
        for history_window in history_windows:
            snapshot_parameters = canonical_parameters(
                FORECAST_DATASET.key,
                {
                    'cluster_id': str(cluster.id),
                    'history_window': history_window,
                },
            )
            if only_due and not _snapshot_due(
                cluster_id=cluster.id,
                dataset_key=FORECAST_DATASET.key,
                parameters=snapshot_parameters,
            ):
                continue
            work_items.append(
                {
                    'cluster_id': cluster.id,
                    'dataset_key': FORECAST_DATASET.key,
                    'parameters': snapshot_parameters,
                    'freshness_minutes': _forecast_freshness_minutes(
                        history_window,
                        freshness_minutes,
                    ),
                    'stale_grace_minutes': min(
                        stale_grace_minutes,
                        FORECAST_DATASET.stale_grace_minutes,
                    ),
                }
            )
    return work_items


def _job_contains_requested_work_item(
    job: JobExecution,
    parameters: dict[str, Any] | None,
) -> bool:
    if not parameters or not parameters.get('cluster_id') or not parameters.get('dataset_key'):
        return False
    requested_cluster = str(parameters['cluster_id'])
    requested_dataset = str(parameters['dataset_key'])
    requested_parameters = canonical_parameters(
        requested_dataset,
        parameters.get('snapshot_parameters'),
    )
    payload = job.payload_json or {}
    for item in payload.get('work_items') or []:
        if not isinstance(item, dict):
            continue
        if str(item.get('cluster_id')) != requested_cluster:
            continue
        if str(item.get('dataset_key')) != requested_dataset:
            continue
        existing_parameters = canonical_parameters(
            requested_dataset,
            item.get('parameters'),
        )
        if existing_parameters == requested_parameters:
            return True
    return False


def _dispatch(
    *,
    policy: JobPolicy,
    trigger_type: str,
    requested_by_user_id: int | None,
    parameters: dict[str, Any] | None,
    forecasting: bool,
) -> RegisteredJobDispatchResult:
    operation = 'materialize_forecast' if forecasting else 'materialize_analytics'
    job_type = 'forecast_materialization' if forecasting else 'analytics_materialization'
    if trigger_type == 'on_demand':
        fleet_job = _active_job(job_type, scope_key='all')
        if fleet_job is not None and _job_contains_requested_work_item(
            fleet_job,
            parameters,
        ):
            return RegisteredJobDispatchResult(
                status='active',
                message='The active fleet materialization job already includes this snapshot.',
                job=fleet_job,
                created=False,
            )

    if forecasting:
        clusters = _metrics_source_eligible_clusters()
    else:
        clusters, metrics_source_cluster_ids = _analytics_eligible_clusters()
    if not clusters:
        return RegisteredJobDispatchResult(
            status='blocked',
            message=('No cluster has an eligible Metrics Source or Alertmanager integration for this job.'),
        )
    only_due = trigger_type == 'scheduled'
    eligibility_diagnostics: list[str] = []
    work_items = (
        _forecast_work_items(
            policy,
            parameters,
            clusters=clusters,
            only_due=only_due,
            eligibility_diagnostics=eligibility_diagnostics,
        )
        if forecasting
        else _analytics_work_items(
            policy,
            parameters,
            clusters=clusters,
            only_due=only_due,
            metrics_source_cluster_ids=metrics_source_cluster_ids,
            eligibility_diagnostics=eligibility_diagnostics,
        )
    )
    if not work_items:
        if only_due and not eligibility_diagnostics:
            message = 'All configured snapshots are still within their freshness windows.'
            status = 'current'
        elif eligibility_diagnostics:
            detail = ' | '.join(eligibility_diagnostics[:3])
            message = f'No analytics snapshot could be queued because source eligibility failed. {detail}'
            status = 'blocked'
        else:
            message = 'No configured dataset has an eligible source and capability contract.'
            status = 'blocked'
        return RegisteredJobDispatchResult(status=status, message=message)
    work_items.sort(key=_work_item_sort_key)
    soft_time_limit, hard_time_limit, estimated_seconds = _effective_task_limits(
        work_items,
        forecasting=forecasting,
    )
    task = materialize_forecast_snapshots if forecasting else materialize_analytics_snapshots
    queue_key = 'FORECASTING_CELERY_QUEUE' if forecasting else 'ANALYTICS_CELERY_QUEUE'
    queue_name = current_app.config[queue_key]
    workload_class = 'forecasting' if forecasting else 'analytics'
    scope_type = 'forecast_fleet' if forecasting else 'analytics_fleet'
    scope_key = str(parameters.get('cluster_id')) if parameters and parameters.get('cluster_id') else 'all'
    resource_group = f'{operation}:{scope_key}'
    admission_parameters: dict[str, Any] = {'scope': scope_key}
    if parameters:
        admission_parameters['request'] = normalize_parameters(parameters)
    job, created = enqueue_canonical_job(
        task=task,
        task_kwargs={'work_items': work_items},
        job_type=job_type,
        operation=operation,
        queue_name=queue_name,
        workload_class=workload_class,
        requested_by_user_id=requested_by_user_id,
        resource_group=resource_group,
        parameters=admission_parameters,
        payload={
            'trigger_type': trigger_type,
            'work_item_count': len(work_items),
            'work_items': work_items,
            'estimated_duration_seconds': estimated_seconds,
            'soft_time_limit_seconds': soft_time_limit,
            'hard_time_limit_seconds': hard_time_limit,
        },
        scope_type=scope_type,
        scope_key=scope_key,
        max_attempts=2,
        soft_time_limit_seconds=soft_time_limit,
        hard_time_limit_seconds=hard_time_limit,
    )
    return RegisteredJobDispatchResult(
        status='queued' if created else 'active',
        message=(
            f'{len(work_items)} snapshot requests were queued.'
            if created
            else 'An equivalent materialization job is already active.'
        ),
        job=job,
        created=created,
    )


def dispatch_analytics_materialization(
    *, requested_by_user_id: int | None, trigger_type: str, parameters: dict[str, Any] | None = None
) -> RegisteredJobDispatchResult:
    from app.jobs.policies.service import get_or_create_job_policy

    return _dispatch(
        policy=get_or_create_job_policy('analytics.materialize'),
        trigger_type=trigger_type,
        requested_by_user_id=requested_by_user_id,
        parameters=parameters,
        forecasting=False,
    )


def dispatch_forecast_materialization(
    *, requested_by_user_id: int | None, trigger_type: str, parameters: dict[str, Any] | None = None
) -> RegisteredJobDispatchResult:
    from app.jobs.policies.service import get_or_create_job_policy

    return _dispatch(
        policy=get_or_create_job_policy('analytics.forecast.materialize'),
        trigger_type=trigger_type,
        requested_by_user_id=requested_by_user_id,
        parameters=parameters,
        forecasting=True,
    )


def _active_job(job_type: str, *, scope_key: str | None = None) -> JobExecution | None:
    query = JobExecution.query.filter(
        JobExecution.job_type == job_type,
        JobExecution.status.in_(ACTIVE_JOB_STATUSES),
        JobExecution.completed_at.is_(None),
    )
    if scope_key is not None:
        query = query.filter(JobExecution.scope_key == scope_key)
    return query.order_by(JobExecution.created_at.desc()).first()


def _snapshot_health(
    *,
    clusters: list[Cluster],
    datasets: tuple[Any, ...],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    dataset_by_key = {dataset.key: dataset for dataset in datasets}
    rows = AnalyticsSnapshot.query.filter(
        AnalyticsSnapshot.cluster_id.in_([cluster.id for cluster in clusters] or ['']),
        AnalyticsSnapshot.dataset_key.in_(list(dataset_by_key) or ['']),
    ).all()
    counts = {'current': 0, 'stale': 0, 'expired': 0, 'failed': 0}
    latest_failure = None
    for snapshot in rows:
        if snapshot.status == 'failed':
            counts['failed'] += 1
            if snapshot.last_error and (
                latest_failure is None
                or (snapshot.last_attempt_at or snapshot.updated_at)
                > (latest_failure.last_attempt_at or latest_failure.updated_at)
            ):
                latest_failure = snapshot
        if snapshot.payload_json is None or snapshot.generated_at is None:
            continue
        expires_at = snapshot.expires_at or snapshot.generated_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        dataset = dataset_by_key.get(snapshot.dataset_key)
        grace_minutes = snapshot.stale_grace_minutes or (dataset.stale_grace_minutes if dataset is not None else 0)
        stale_deadline = expires_at + timedelta(minutes=grace_minutes)
        if now <= expires_at:
            counts['current'] += 1
        elif now <= stale_deadline:
            counts['stale'] += 1
        else:
            counts['expired'] += 1
    return {
        **counts,
        'total': len(rows),
        'latest_failure': (
            {
                'dataset_key': latest_failure.dataset_key,
                'error': latest_failure.last_error,
                'attempted_at': latest_failure.last_attempt_at,
            }
            if latest_failure is not None
            else None
        ),
    }


def _context(policy: JobPolicy, *, forecasting: bool) -> dict[str, Any]:
    clusters = _metrics_source_eligible_clusters() if forecasting else _analytics_eligible_clusters()[0]
    datasets = (FORECAST_DATASET,) if forecasting else list_analytics_datasets()
    job_type = 'forecast_materialization' if forecasting else 'analytics_materialization'
    operation = 'materialize_forecast' if forecasting else 'materialize_analytics'
    jobs = JobExecution.query.filter_by(job_type=job_type, operation=operation)
    active_job = _active_job(job_type)
    recent_jobs = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).limit(5).all()
    latest = recent_jobs[0] if recent_jobs else None
    snapshot_count = AnalyticsSnapshot.query.filter(
        AnalyticsSnapshot.cluster_id.in_([cluster.id for cluster in clusters] or ['']),
        AnalyticsSnapshot.dataset_key.in_([dataset.key for dataset in datasets]),
        AnalyticsSnapshot.payload_json.isnot(None),
    ).count()
    snapshot_health = _snapshot_health(
        clusters=clusters,
        datasets=tuple(datasets),
    )

    if active_job is not None:
        configuration_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
        }
        execution_state = {
            'label': 'Execution Active',
            'tone': 'pending',
            'icon': 'loader-circle',
            'description': 'A materialization worker is processing snapshot requests.',
        }
    elif not clusters:
        configuration_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
        execution_state = {
            'label': 'Blocked',
            'tone': 'warning',
            'icon': 'shield-alert',
            'description': 'No eligible source binding is available for this job.',
        }
    elif policy.enabled:
        configuration_state = {
            'label': 'Enabled',
            'tone': 'normal',
            'icon': 'circle-check',
        }
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Eligible clusters are ready for materialization.',
        }
    else:
        configuration_state = {
            'label': 'Manual Only',
            'tone': 'unknown',
            'icon': 'mouse-pointer-click',
        }
        execution_state = {
            'label': 'Ready',
            'tone': 'normal',
            'icon': 'circle-check',
            'description': 'Manual materialization is available for eligible clusters.',
        }

    return {
        'eligible_cluster_count': len(clusters),
        'registered_cluster_count': Cluster.query.count(),
        'dataset_count': len(datasets),
        'snapshot_count': snapshot_count,
        'snapshot_health': snapshot_health,
        'configuration_state': configuration_state,
        'execution_state': execution_state,
        'active_job': present_job_execution(active_job) if active_job is not None else None,
        'latest_job': present_job_execution(latest) if latest is not None else None,
        'recent_jobs': [present_job_execution(job) for job in recent_jobs],
        'queue_name': current_app.config['FORECASTING_CELERY_QUEUE' if forecasting else 'ANALYTICS_CELERY_QUEUE'],
        'policy_configuration': policy.configuration_json or {},
        'generated_at': datetime.now(UTC),
    }


def build_analytics_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    return _context(policy, forecasting=False)


def build_forecast_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    return _context(policy, forecasting=True)
