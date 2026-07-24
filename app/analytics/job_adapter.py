from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import current_app

from app.analytics.materialization.catalog import FORECAST_DATASET, list_analytics_datasets
from app.analytics.materialization.service import get_snapshot, normalize_parameters
from app.analytics.tasks import materialize_analytics_snapshots, materialize_forecast_snapshots
from app.jobs.definitions.base import RegisteredJobDispatchResult
from app.jobs.dispatcher import enqueue_canonical_job
from app.models import AnalyticsSnapshot, Cluster
from app.models.job import JobExecution, JobPolicy
from app.prometheus.repository import resolve_instance_for_cluster


def _eligible_clusters() -> list[Cluster]:
    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    return [
        cluster
        for cluster in clusters
        if (instance := resolve_instance_for_cluster(cluster.id)) is not None and instance.endpoint.strip()
    ]


def _range_freshness_minutes(value: str | None, base_minutes: int) -> int:
    minimum_by_range = {
        '1h': 5,
        '6h': 10,
        '12h': 15,
        '24h': 20,
        '7d': 60,
        '30d': 180,
        '60d': 360,
    }
    return max(base_minutes, minimum_by_range.get(value or '', base_minutes))


def _forecast_freshness_minutes(history_window: str, base_minutes: int) -> int:
    minimum_by_history = {'30d': 120, '90d': 360}
    return max(base_minutes, minimum_by_history.get(history_window, base_minutes))


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
) -> list[dict[str, Any]]:
    configuration = policy.configuration_json or {}
    freshness_minutes = int(configuration.get('freshness_minutes') or 20)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 1440)
    if parameters and parameters.get('dataset_key') and parameters.get('cluster_id'):
        return [
            {
                'cluster_id': str(parameters['cluster_id']),
                'dataset_key': str(parameters['dataset_key']),
                'parameters': normalize_parameters(parameters.get('snapshot_parameters')),
                'freshness_minutes': freshness_minutes,
                'stale_grace_minutes': stale_grace_minutes,
            }
        ]
    ranges = _configured_values(
        policy,
        'time_ranges',
        ['1h', '6h', '12h', '24h', '7d', '30d', '60d'],
    )
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
        for dataset in list_analytics_datasets():
            for default_parameters in dataset.default_parameters:
                time_range = default_parameters.get('time_range')
                trend_range = trend_range_by_hours.get(str(default_parameters.get('trend_hours') or ''))
                selected_range = time_range or trend_range
                if selected_range and selected_range not in ranges:
                    continue
                snapshot_parameters = {
                    'cluster_id': str(cluster.id),
                    **default_parameters,
                }
                item_freshness = _range_freshness_minutes(selected_range, freshness_minutes)
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
                        'stale_grace_minutes': stale_grace_minutes,
                    }
                )
    return work_items


def _forecast_work_items(
    policy: JobPolicy,
    parameters: dict[str, Any] | None,
    *,
    clusters: list[Cluster],
    only_due: bool,
) -> list[dict[str, Any]]:
    configuration = policy.configuration_json or {}
    freshness_minutes = int(configuration.get('freshness_minutes') or 120)
    stale_grace_minutes = int(configuration.get('stale_grace_minutes') or 4320)
    if parameters and parameters.get('dataset_key') and parameters.get('cluster_id'):
        return [
            {
                'cluster_id': str(parameters['cluster_id']),
                'dataset_key': FORECAST_DATASET.key,
                'parameters': normalize_parameters(parameters.get('snapshot_parameters')),
                'freshness_minutes': freshness_minutes,
                'stale_grace_minutes': stale_grace_minutes,
            }
        ]
    history_windows = _configured_values(policy, 'history_windows', ['30d', '90d'])
    horizons = _configured_values(policy, 'forecast_horizons', ['90d', '180d', '365d'])
    work_items: list[dict[str, Any]] = []
    for cluster in clusters:
        for history_window in history_windows:
            for horizon in horizons:
                snapshot_parameters = {
                    'cluster_id': str(cluster.id),
                    'history_window': history_window,
                    'forecast_horizon': horizon,
                    'resource': 'all',
                    'method': 'linear',
                }
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
                        'stale_grace_minutes': stale_grace_minutes,
                    }
                )
    return work_items


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
        if fleet_job is not None:
            return RegisteredJobDispatchResult(
                status='active',
                message='A fleet materialization job is already preparing this dataset family.',
                job=fleet_job,
                created=False,
            )

    clusters = _eligible_clusters()
    if not clusters:
        return RegisteredJobDispatchResult(
            status='blocked',
            message='No cluster has an eligible Prometheus integration for this job.',
        )
    only_due = trigger_type == 'scheduled'
    work_items = (
        _forecast_work_items(policy, parameters, clusters=clusters, only_due=only_due)
        if forecasting
        else _analytics_work_items(policy, parameters, clusters=clusters, only_due=only_due)
    )
    if not work_items:
        return RegisteredJobDispatchResult(
            status='current',
            message='All configured snapshots are still within their freshness windows.',
        )
    task = materialize_forecast_snapshots if forecasting else materialize_analytics_snapshots
    queue_name = current_app.config['FORECASTING_CELERY_QUEUE' if forecasting else 'ANALYTICS_CELERY_QUEUE']
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
        },
        scope_type=scope_type,
        scope_key=scope_key,
        max_attempts=2,
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
        JobExecution.status.in_({'queued', 'running', 'retrying', 'cancel_requested'}),
    )
    if scope_key is not None:
        query = query.filter(JobExecution.scope_key == scope_key)
    return query.order_by(JobExecution.created_at.desc()).first()


def _context(policy: JobPolicy, *, forecasting: bool) -> dict[str, Any]:
    clusters = _eligible_clusters()
    datasets = (FORECAST_DATASET,) if forecasting else list_analytics_datasets()
    job_type = 'forecast_materialization' if forecasting else 'analytics_materialization'
    operation = 'materialize_forecast' if forecasting else 'materialize_analytics'
    latest = (
        JobExecution.query.filter_by(job_type=job_type, operation=operation)
        .order_by(JobExecution.created_at.desc())
        .first()
    )
    snapshot_count = AnalyticsSnapshot.query.filter(
        AnalyticsSnapshot.cluster_id.in_([cluster.id for cluster in clusters] or ['']),
        AnalyticsSnapshot.dataset_key.in_([dataset.key for dataset in datasets]),
        AnalyticsSnapshot.payload_json.isnot(None),
    ).count()
    return {
        'eligible_cluster_count': len(clusters),
        'registered_cluster_count': Cluster.query.count(),
        'dataset_count': len(datasets),
        'snapshot_count': snapshot_count,
        'active_job': _active_job(job_type),
        'latest_job': latest,
        'queue_name': current_app.config['FORECASTING_CELERY_QUEUE' if forecasting else 'ANALYTICS_CELERY_QUEUE'],
        'policy_configuration': policy.configuration_json or {},
        'generated_at': datetime.now(UTC),
    }


def build_analytics_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    return _context(policy, forecasting=False)


def build_forecast_materialization_context(policy: JobPolicy) -> dict[str, Any]:
    return _context(policy, forecasting=True)
