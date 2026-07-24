from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from celery import shared_task
from flask import current_app

from app.analytics.materialization.catalog import get_dataset
from app.analytics.materialization.service import fail_snapshot, normalize_parameters, store_snapshot
from app.jobs.execution import JobCancellationRequested, JobExecutionContext
from app.models import Cluster


def _task_id(job_execution_id: int, fallback_task_id: str | None) -> str:
    from app.models.job import JobExecution

    job = JobExecution.query.get(job_execution_id)
    return str(job.celery_task_id if job and job.celery_task_id else fallback_task_id or '')


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

    try:
        for index, item in enumerate(work_items, start=1):
            cluster_id = int(item['cluster_id'])
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
            try:
                query_string = urlencode(parameters)
                with current_app.test_request_context(f'/analytics/materialize?{query_string}'):
                    context = dataset.builder(parameters)
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
            except Exception as exc:
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
