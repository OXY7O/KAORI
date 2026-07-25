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

from app.analytics.materialization.catalog import get_dataset
from app.analytics.materialization.service import (
    fail_snapshot,
    mark_snapshot_pending,
    normalize_parameters,
    store_snapshot,
)
from app.extensions.db import db
from app.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.models import Cluster


class AnalyticsDatasetTimeoutError(TimeoutError):
    pass


def _dataset_timeout_seconds(dataset_key: str) -> int:
    config_key = (
        'FORECASTING_DATASET_TIMEOUT_SECONDS'
        if dataset_key == 'analytics.forecast'
        else 'ANALYTICS_DATASET_TIMEOUT_SECONDS'
    )
    default = 600 if dataset_key == 'analytics.forecast' else 300
    return int(current_app.config.get(config_key, default))


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
        raise AnalyticsDatasetTimeoutError(
            f'{dataset_key} exceeded its {timeout_seconds}-second execution limit.'
        )

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
        try:
            fail_snapshot(
                cluster_id=str(item['cluster_id']),
                dataset_key=str(item['dataset_key']),
                parameters=normalize_parameters(item.get('parameters')),
                error=error,
                job_execution_id=job_execution_id,
            )
        except Exception:
            current_app.logger.exception(
                'Could not mark timed-out analytics snapshot as failed for %s on cluster %s.',
                item.get('dataset_key'),
                item.get('cluster_id'),
            )


def _materialize(
    *,
    job_execution_id: int,
    work_items: list[dict[str, Any]],
    fallback_task_id: str | None,
) -> dict[str, Any]:
    task_id = _task_id(job_execution_id, fallback_task_id)
    lifecycle = JobExecutionContext(task_id)
    lifecycle.start(message='Preparing analytics materialization', total=len(work_items))
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
                message=f'Generating {dataset.label} for {cluster_name}',
            )
            mark_snapshot_pending(
                cluster_id=cluster_id,
                dataset_key=dataset_key,
                parameters=parameters,
                job_execution_id=job_execution_id,
            )
            try:
                query_string = urlencode(parameters)
                timeout_seconds = _dataset_timeout_seconds(dataset_key)
                with _dataset_time_limit(
                    dataset_key=dataset_key,
                    timeout_seconds=timeout_seconds,
                ):
                    with current_app.test_request_context(
                        f'/analytics/materialize?{query_string}'
                    ):
                        context = dataset.builder(parameters)
                blocker = context.get('dependency_blocker') if isinstance(context, dict) else None
                if blocker:
                    if isinstance(blocker, dict):
                        blocker_title = str(
                            blocker.get('title') or 'Analytics dependency unavailable'
                        )
                        blocker_detail = str(
                            blocker.get('diagnostic_detail')
                            or blocker.get('description')
                            or blocker.get('badge')
                            or ''
                        )
                    else:
                        blocker_title = str(
                            getattr(blocker, 'title', '') or 'Analytics dependency unavailable'
                        )
                        blocker_detail = str(
                            getattr(blocker, 'diagnostic_detail', '')
                            or getattr(blocker, 'description', '')
                            or getattr(blocker, 'badge', '')
                        )
                    raise RuntimeError(
                        f'{blocker_title}: {blocker_detail}'.rstrip(': ')
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
                succeeded += 1
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception(
                    'Analytics materialization failed for %s on cluster %s.',
                    dataset_key,
                    cluster_id,
                )
                fail_snapshot(
                    cluster_id=cluster_id,
                    dataset_key=dataset_key,
                    parameters=parameters,
                    error=exc,
                    job_execution_id=job_execution_id,
                )
                failed += 1
                failures.append({'dataset_key': dataset_key, 'cluster_id': str(cluster_id), 'error': str(exc)[:255]})
            lifecycle.checkpoint(
                current=index,
                total=len(work_items),
                message=f'Generated {index} of {len(work_items)} analytics snapshots',
            )
    except JobCancellationRequested:
        lifecycle.canceled()
        return {'status': 'canceled', 'succeeded': succeeded, 'failed': failed}
    except SoftTimeLimitExceeded as exc:
        message = 'Analytics materialization exceeded its worker time limit.'
        _fail_unfinished_work_items(
            work_items=work_items[max(current_index - 1, 0):],
            job_execution_id=job_execution_id,
            error=message,
        )
        lifecycle.fail(message, error_code='analytics_materialization_timeout')
        raise exc
    except Exception as exc:
        lifecycle.fail(exc, error_code='analytics_materialization_failed')
        raise

    summary = {
        'total': len(work_items),
        'succeeded': succeeded,
        'failed': failed,
        'failures': failures[:20],
    }
    if failed and not succeeded:
        lifecycle.fail(
            RuntimeError('All analytics snapshot requests failed.'),
            error_code='analytics_materialization_all_failed',
        )
        return summary
    lifecycle.succeed(
        result_summary=summary,
        result_type='analytics_snapshots',
        result_reference='analytics_snapshots',
        partial=failed > 0,
    )
    return summary


@shared_task(
    bind=True,
    name='app.analytics.tasks.materialize_analytics_snapshots',
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
    name='app.analytics.tasks.materialize_forecast_snapshots',
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
