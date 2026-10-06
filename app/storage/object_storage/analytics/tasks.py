from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError

from app.common.analytics.metrics import MetricsSourceError
from app.extensions.db import db
from app.models.object_storage import ObjectStorageSystem
from app.platform_operations.jobs.execution import JobExecutionContext
from app.storage.object_storage.analytics.materialization import (
    fail_analytics_snapshot,
    materialize_forecast,
    store_analytics_snapshot,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='app.storage.object_storage.analytics.tasks.materialize_object_storage_analytics',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_object_storage_analytics(
    self,
    *,
    work_items: list[dict[str, Any]],
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    """Collect and commit reusable Object Storage operational analytics snapshots."""

    from app.storage.object_storage.analytics.service import build_analytics_snapshot_payload

    task_id = str(self.request.id)
    lifecycle = JobExecutionContext(task_id, job_execution_id)
    total = len(work_items)
    lifecycle.start(
        message='Preparing Object Storage analytics materialization.',
        total=total,
        percent=1,
        stage='Preparing Analytics',
        target='Object Storage Estate',
    )
    succeeded = 0
    failures: list[dict[str, str]] = []
    try:
        for index, item in enumerate(work_items, start=1):
            system_id = str(item['system_id'])
            time_range = str(item['time_range'])
            freshness_minutes = int(item.get('freshness_minutes') or 15)
            stale_grace_minutes = int(item.get('stale_grace_minutes') or 1440)
            system = db.session.get(ObjectStorageSystem, system_id)
            if system is None:
                failures.append(
                    {
                        'system_id': system_id,
                        'time_range': time_range,
                        'error': 'Object Storage system no longer exists.',
                    }
                )
                continue
            percent = min(5 + int(((index - 1) / max(total, 1)) * 90), 95)
            lifecycle.checkpoint(
                current=index - 1,
                total=total,
                percent=percent,
                stage='Collecting Analytics Evidence',
                target=f'{system.name} · {time_range}',
                message=f'Collecting {time_range} Object Storage analytics evidence for {system.name}.',
            )
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': index - 1,
                    'total': total,
                    'percent': percent,
                    'system_id': system_id,
                    'system_name': system.name,
                    'time_range': time_range,
                },
            )
            try:
                payload = build_analytics_snapshot_payload(system=system, time_range=time_range)
                store_analytics_snapshot(
                    system_id=system.id,
                    time_range=time_range,
                    payload=payload,
                    freshness_minutes=freshness_minutes,
                    stale_grace_minutes=stale_grace_minutes,
                    job_execution_id=job_execution_id,
                )
                succeeded += 1
            except (MetricsSourceError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
                db.session.rollback()
                logger.exception(
                    'Object Storage analytics materialization failed for %s (%s).',
                    system.name,
                    time_range,
                )
                try:
                    fail_analytics_snapshot(
                        system_id=system.id,
                        time_range=time_range,
                        error=exc,
                        freshness_minutes=freshness_minutes,
                        stale_grace_minutes=stale_grace_minutes,
                        job_execution_id=job_execution_id,
                    )
                except SQLAlchemyError:
                    db.session.rollback()
                    logger.exception('Could not persist Object Storage analytics failure state.')
                failures.append(
                    {
                        'system_id': system_id,
                        'system_name': system.name,
                        'time_range': time_range,
                        'error': str(exc)[:1000],
                    }
                )

        summary = {
            'total': total,
            'succeeded': succeeded,
            'failed': len(failures),
            'failures': failures[:20],
        }
        if failures and not succeeded:
            lifecycle.fail(
                RuntimeError('All Object Storage analytics materializations failed.'),
                error_code='object_storage_analytics_all_failed',
            )
        else:
            lifecycle.succeed(
                result_summary=summary,
                result_type='object_storage_analytics_snapshots',
                result_reference='object_storage_analytics_snapshots',
                partial=bool(failures),
            )
        return summary
    except (MetricsSourceError, RuntimeError, SQLAlchemyError) as exc:
        db.session.rollback()
        lifecycle.fail(exc, error_code='object_storage_analytics_worker_failed')
        raise


@shared_task(
    bind=True,
    name='app.storage.object_storage.analytics.tasks.materialize_object_storage_forecasts',
    acks_late=True,
    reject_on_worker_lost=True,
)
def materialize_object_storage_forecasts(
    self,
    *,
    work_items: list[dict[str, Any]],
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    lifecycle = JobExecutionContext(task_id, job_execution_id)
    total = len(work_items)
    lifecycle.start(
        message='Preparing Object Storage forecast materialization.',
        total=total,
        percent=1,
        stage='Preparing Forecast',
        target='Object Storage Estate',
    )
    succeeded = 0
    failures: list[dict[str, str]] = []
    try:
        for index, item in enumerate(work_items, start=1):
            system_id = str(item['system_id'])
            history_window = str(item['history_window'])
            system = db.session.get(ObjectStorageSystem, system_id)
            if system is None:
                failures.append(
                    {
                        'system_id': system_id,
                        'history_window': history_window,
                        'error': 'Object Storage system no longer exists.',
                    }
                )
                continue
            percent = min(5 + int(((index - 1) / max(total, 1)) * 90), 95)
            lifecycle.checkpoint(
                current=index - 1,
                total=total,
                percent=percent,
                stage='Materializing Forecast',
                target=f'{system.name} · {history_window}',
                message=f'Building {history_window} Object Storage capacity forecast for {system.name}.',
            )
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': index - 1,
                    'total': total,
                    'percent': percent,
                    'system_id': system_id,
                    'system_name': system.name,
                    'history_window': history_window,
                },
            )
            try:
                materialize_forecast(
                    system=system,
                    history_window=history_window,
                    freshness_minutes=int(item.get('freshness_minutes') or 120),
                    stale_grace_minutes=int(item.get('stale_grace_minutes') or 4320),
                    job_execution_id=job_execution_id,
                )
                succeeded += 1
            except (MetricsSourceError, RuntimeError, SQLAlchemyError) as exc:
                db.session.rollback()
                logger.exception(
                    'Object Storage forecast materialization failed for %s (%s).',
                    system.name,
                    history_window,
                )
                failures.append(
                    {
                        'system_id': system_id,
                        'system_name': system.name,
                        'history_window': history_window,
                        'error': str(exc)[:1000],
                    }
                )

        summary = {
            'total': total,
            'succeeded': succeeded,
            'failed': len(failures),
            'failures': failures[:20],
        }
        if failures and not succeeded:
            lifecycle.fail(
                RuntimeError('All Object Storage forecast materializations failed.'),
                error_code='object_storage_forecast_all_failed',
            )
        else:
            lifecycle.succeed(
                result_summary=summary,
                result_type='object_storage_forecast_snapshots',
                result_reference='object_storage_forecast_snapshots',
                partial=bool(failures),
            )
        return summary
    except (MetricsSourceError, RuntimeError, SQLAlchemyError) as exc:
        db.session.rollback()
        lifecycle.fail(exc, error_code='object_storage_forecast_worker_failed')
        raise
