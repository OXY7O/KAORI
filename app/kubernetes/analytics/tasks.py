from __future__ import annotations

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from threading import current_thread, main_thread
from typing import Any
from urllib.parse import urlencode

from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from flask import current_app

from app.common.provider_query_runtime import provider_query_runtime
from app.extensions.db import db
from app.kubernetes.analytics.materialization.catalog import (
    dataset_task_budget_seconds,
    get_dataset,
)
from app.kubernetes.analytics.materialization.errors import (
    AnalyticsDatasetTimeoutError,
    AnalyticsDependencyError,
    classify_analytics_failure,
)
from app.kubernetes.analytics.materialization.identity import normalize_parameters
from app.kubernetes.analytics.materialization.service import (
    fail_snapshot,
    mark_snapshot_pending,
    store_snapshot,
)
from app.kubernetes.analytics.materialization.source_lock import analytics_source_lock
from app.models import Cluster
from app.platform_operations.jobs.execution import JobCancellationRequested, JobExecutionContext


def _dataset_timeout_seconds(
    dataset_key: str,
    parameters: dict[str, Any] | None,
) -> int:
    forecasting = dataset_key == 'analytics.forecast'
    config_key = 'FORECASTING_DATASET_TIMEOUT_SECONDS' if forecasting else 'ANALYTICS_DATASET_TIMEOUT_SECONDS'
    configured = int(current_app.config.get(config_key, 600 if forecasting else 300))
    estimated = dataset_task_budget_seconds(dataset_key, parameters)
    maximum = 3600 if forecasting else 1800
    return min(max(configured, estimated), maximum)


@contextmanager
def _dataset_time_limit(
    *,
    dataset_key: str,
    timeout_seconds: int,
) -> Iterator[None]:
    """Bound one dataset builder without terminating the whole batch.

    Celery workers run the task inside a Linux fork child where SIGALRM can
    interrupt a blocked HTTP read or an unexpectedly long local transform. If
    the runtime does not support SIGALRM, the global Celery soft limit remains
    the fallback boundary.
    """

    if (
        timeout_seconds <= 0
        or current_thread() is not main_thread()
        or not hasattr(signal, 'SIGALRM')
        or not hasattr(signal, 'setitimer')
    ):
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def handle_timeout(_signum, _frame) -> None:
        raise AnalyticsDatasetTimeoutError(f'{dataset_key} exceeded its {timeout_seconds}-second execution limit.')

    signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _task_id(job_execution_id: int, fallback_task_id: str | None) -> str:
    from app.models.job import JobExecution

    job = JobExecution.query.get(job_execution_id)
    return str(job.celery_task_id if job and job.celery_task_id else fallback_task_id or '')


def _fail_unfinished_work_items(
    *,
    work_items: list[dict[str, Any]],
    job_execution_id: int,
    error: Exception | str,
) -> None:
    for item in work_items:
        dataset_key = str(item.get('dataset_key') or '')
        cluster_id = str(item.get('cluster_id') or '')
        try:
            dataset = get_dataset(dataset_key)
            cluster = Cluster.query.get(cluster_id)
            failure = classify_analytics_failure(
                error,
                dataset_label=dataset.label,
                cluster_name=cluster.name if cluster is not None else f'Cluster {cluster_id}',
            )
            fail_snapshot(
                cluster_id=cluster_id,
                dataset_key=dataset_key,
                parameters=normalize_parameters(item.get('parameters')),
                error=failure.log_message(),
                job_execution_id=job_execution_id,
            )
        except Exception:
            current_app.logger.exception(
                'Could not mark unfinished analytics snapshot as failed for %s on cluster %s.',
                dataset_key,
                cluster_id,
            )


def _dependency_blocker_message(blocker: Any) -> str:
    if isinstance(blocker, dict):
        title = str(blocker.get('title') or 'Analytics dependency unavailable')
        detail = str(blocker.get('diagnostic_detail') or blocker.get('description') or blocker.get('badge') or '')
    else:
        title = str(getattr(blocker, 'title', '') or 'Analytics dependency unavailable')
        detail = str(
            getattr(blocker, 'diagnostic_detail', '')
            or getattr(blocker, 'description', '')
            or getattr(blocker, 'badge', '')
        )
    return f'{title}: {detail}'.rstrip(': ')


def _record_materialization_failure(
    exc: Exception,
    dataset: Any,
    cluster_name: str,
    dataset_key: str,
    cluster_id: str,
    job_execution_id: int,
    parameters: dict[str, Any],
    query_runtime: Any,
) -> dict[str, str]:
    db.session.rollback()
    failure = classify_analytics_failure(exc, dataset_label=dataset.label, cluster_name=cluster_name)
    runtime_summary = query_runtime.summary() if query_runtime is not None else {}
    current_app.logger.exception(
        'Analytics materialization failed [%s] for %s on cluster %s: %s',
        failure.code,
        dataset_key,
        cluster_id,
        failure.detail,
        extra={
            'analytics_failure_code': failure.code,
            'analytics_failure_retryable': failure.retryable,
            'analytics_failure_remediation': failure.remediation,
            'dataset_key': dataset_key,
            'cluster_id': cluster_id,
            'job_execution_id': job_execution_id,
            **runtime_summary,
        },
    )
    fail_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=parameters,
        error=failure.log_message(),
        job_execution_id=job_execution_id,
    )
    return {
        'dataset_key': dataset_key,
        'cluster_id': cluster_id,
        'code': failure.code,
        'title': failure.title,
        'error': failure.detail[:1000],
        'remediation': failure.remediation,
        'retryable': str(failure.retryable).lower(),
        'query_count': str(runtime_summary.get('query_count', 0)),
        'retry_count': str(runtime_summary.get('retry_count', 0)),
        'query_duration_ms': str(runtime_summary.get('query_duration_ms', 0)),
    }


def _finish_materialization_batch(
    *,
    lifecycle: JobExecutionContext,
    work_items: list[dict[str, Any]],
    succeeded: int,
    failed: int,
    failures: list[dict[str, str]],
    job_execution_id: int,
) -> dict[str, Any]:
    summary = {
        'total': len(work_items),
        'succeeded': succeeded,
        'failed': failed,
        'failures': failures[:20],
    }
    current_app.logger.info(
        'Analytics materialization batch finished.',
        extra={
            'job_execution_id': job_execution_id,
            'total': len(work_items),
            'succeeded': succeeded,
            'failed': failed,
            'status': ('failed' if failed and not succeeded else ('partially_succeeded' if failed else 'succeeded')),
        },
    )
    if failed and not succeeded:
        first_failure = failures[0] if failures else {}
        lifecycle.fail(
            RuntimeError(str(first_failure.get('title') or 'All analytics snapshot requests failed.')),
            error_code=str(first_failure.get('code') or 'analytics_materialization_all_failed'),
        )
        return summary
    lifecycle.succeed(
        result_summary=summary,
        result_type='analytics_snapshots',
        result_reference='analytics_snapshots',
        partial=failed > 0,
    )
    return summary


def _batch_percent(index: int, total: int, local_percent: int) -> int:
    completed_fraction = (index - 1) + (max(0, min(local_percent, 100)) / 100)
    return min(2 + int((completed_fraction / max(total, 1)) * 96), 98)


def _materialize(
    *,
    job_execution_id: int,
    work_items: list[dict[str, Any]],
    fallback_task_id: str | None,
) -> dict[str, Any]:
    task_id = _task_id(job_execution_id, fallback_task_id)
    lifecycle = JobExecutionContext(task_id)
    lifecycle.start(
        message='Preparing analytics materialization.',
        total=len(work_items),
        percent=1,
        stage='Preparing Analytics',
        target='Analytics Snapshot Batch',
    )
    succeeded = 0
    failed = 0
    failures: list[dict[str, str]] = []
    current_index = 0
    try:
        for index, item in enumerate(work_items, start=1):
            current_index = index
            cluster_id = str(item['cluster_id'])
            dataset_key = str(item['dataset_key'])
            parameters = normalize_parameters(item.get('parameters'))
            parameters['cluster_id'] = str(cluster_id)
            dataset = get_dataset(dataset_key)
            cluster = Cluster.query.get(cluster_id)
            cluster_name = cluster.name if cluster is not None else f'Cluster {cluster_id}'
            lifecycle.checkpoint(
                current=index - 1,
                total=len(work_items),
                percent=_batch_percent(index, len(work_items), 0),
                stage='Preparing Analytics Dataset',
                target=f'{dataset.label} · {cluster_name}',
                message=f'Preparing {dataset.label} for {cluster_name}.',
            )
            mark_snapshot_pending(
                cluster_id=cluster_id,
                dataset_key=dataset_key,
                parameters=parameters,
                job_execution_id=job_execution_id,
            )
            query_runtime = None
            try:
                query_string = urlencode(parameters)
                timeout_seconds = _dataset_timeout_seconds(dataset_key, parameters)
                current_app.logger.info(
                    'Analytics dataset materialization started.',
                    extra={
                        'dataset_key': dataset_key,
                        'dataset_label': dataset.label,
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'job_execution_id': job_execution_id,
                        'dataset_timeout_seconds': timeout_seconds,
                        'snapshot_parameters': parameters,
                    },
                )
                with provider_query_runtime(
                    dataset_key=dataset_key,
                    cluster_id=cluster_id,
                    job_execution_id=job_execution_id,
                ) as query_runtime:
                    with analytics_source_lock(
                        dataset_key=dataset_key,
                        cluster_id=cluster_id,
                        parameters=parameters,
                    ) as source_lock_wait_ms:
                        query_runtime.source_lock_wait_ms = source_lock_wait_ms
                        if source_lock_wait_ms >= 1000:
                            lifecycle.checkpoint(
                                current=index - 1,
                                total=len(work_items),
                                percent=_batch_percent(index, len(work_items), 15),
                                stage='Waiting for Metrics Source',
                                target=f'{dataset.label} · {cluster_name}',
                                message=f'Waiting for the shared metrics source before generating {dataset.label}.',
                            )
                            current_app.logger.info(
                                'Analytics dataset waited for a shared provider query slot.',
                                extra={
                                    'dataset_key': dataset_key,
                                    'cluster_id': cluster_id,
                                    'job_execution_id': job_execution_id,
                                    'source_lock_wait_ms': source_lock_wait_ms,
                                },
                            )
                        lifecycle.checkpoint(
                            current=index - 1,
                            total=len(work_items),
                            percent=_batch_percent(index, len(work_items), 35),
                            stage='Querying Analytics Sources',
                            target=f'{dataset.label} · {cluster_name}',
                            message=f'Collecting source data for {dataset.label}.',
                        )
                        with _dataset_time_limit(
                            dataset_key=dataset_key,
                            timeout_seconds=timeout_seconds,
                        ):
                            with current_app.test_request_context(f'/analytics/materialize?{query_string}'):
                                context = dataset.builder(parameters)
                    if not isinstance(context, dict):
                        raise TypeError(f'{dataset.key} returned {type(context).__name__}; expected a context mapping.')
                    blocker = context.get('dependency_blocker')
                    if blocker:
                        raise AnalyticsDependencyError(_dependency_blocker_message(blocker))
                    context['analytics_runtime'] = query_runtime.summary()
                    lifecycle.checkpoint(
                        current=index - 1,
                        total=len(work_items),
                        percent=_batch_percent(index, len(work_items), 78),
                        stage='Committing Analytics Snapshot',
                        target=f'{dataset.label} · {cluster_name}',
                        message=f'Persisting the committed {dataset.label} snapshot.',
                    )
                    store_snapshot(
                        cluster_id=cluster_id,
                        dataset_key=dataset_key,
                        parameters=parameters,
                        context=context,
                        job_execution_id=job_execution_id,
                        freshness_minutes=int(item.get('freshness_minutes') or dataset.freshness_minutes),
                        stale_grace_minutes=int(item.get('stale_grace_minutes') or dataset.stale_grace_minutes),
                    )
                    current_app.logger.info(
                        'Analytics snapshot materialized.',
                        extra={
                            **query_runtime.summary(),
                            'dataset_label': dataset.label,
                            'cluster_name': cluster_name,
                        },
                    )
                succeeded += 1
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:
                failed += 1
                failures.append(
                    _record_materialization_failure(
                        exc,
                        dataset,
                        cluster_name,
                        dataset_key,
                        cluster_id,
                        job_execution_id,
                        parameters,
                        query_runtime,
                    )
                )
            lifecycle.checkpoint(
                current=index,
                total=len(work_items),
                percent=_batch_percent(index, len(work_items), 100),
                stage='Analytics Snapshot Completed',
                target=f'{dataset.label} · {cluster_name}',
                message=f'Generated {index} of {len(work_items)} analytics snapshots.',
            )
    except JobCancellationRequested:
        lifecycle.canceled()
        return {'status': 'canceled', 'succeeded': succeeded, 'failed': failed}
    except SoftTimeLimitExceeded as exc:
        message = 'Analytics materialization exceeded its global worker time limit.'
        _fail_unfinished_work_items(
            work_items=work_items[max(current_index - 1, 0) :],
            job_execution_id=job_execution_id,
            error=exc,
        )
        lifecycle.fail(message, error_code='analytics_materialization_timeout')
        raise exc
    except Exception as exc:
        lifecycle.fail(exc, error_code='analytics_materialization_failed')
        raise
    return _finish_materialization_batch(
        lifecycle=lifecycle,
        work_items=work_items,
        succeeded=succeeded,
        failed=failed,
        failures=failures,
        job_execution_id=job_execution_id,
    )


@shared_task(
    bind=True,
    name='app.kubernetes.analytics.tasks.materialize_analytics_snapshots',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_analytics_snapshots(
    self,
    *,
    job_execution_id: int,
    work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return _materialize(
        job_execution_id=job_execution_id,
        work_items=work_items,
        fallback_task_id=getattr(self.request, 'id', None),
    )


@shared_task(
    bind=True,
    name='app.kubernetes.analytics.tasks.materialize_forecast_snapshots',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_forecast_snapshots(
    self,
    *,
    job_execution_id: int,
    work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return _materialize(
        job_execution_id=job_execution_id,
        work_items=work_items,
        fallback_task_id=getattr(self.request, 'id', None),
    )
