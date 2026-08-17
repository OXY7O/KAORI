from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from celery.result import AsyncResult
from flask import current_app
from redis import Redis

from app.models.job import JobExecution, JobExecutionSubscriber
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES

INDIVIDUAL_CLUSTER_SYNC_TASK_NAME = 'app.kubernetes.cluster.tasks.sync_single_cluster'
INDIVIDUAL_CLUSTER_SYNC_QUEUE = 'inventory'
INDIVIDUAL_SYNC_ACTIVE_PREFIX = 'kaori:cluster-individual-sync:active:'
INDIVIDUAL_SYNC_METADATA_PREFIX = 'kaori:cluster-individual-sync:metadata:'
INDIVIDUAL_SYNC_DISMISSED_PREFIX = 'kaori:cluster-individual-sync:dismissed:'
ACTIVE_CELERY_STATES = {'PENDING', 'RECEIVED', 'STARTED', 'PROGRESS', 'RETRY'}


def _redis_client() -> Redis:
    redis_url = current_app.config.get('REDIS_URL')
    if not redis_url:
        raise RuntimeError('REDIS_URL is required for persistent individual cluster synchronization.')
    return Redis.from_url(redis_url, decode_responses=True)


def _result_ttl_seconds() -> int:
    return max(int(current_app.config.get('CELERY_RESULT_EXPIRES_SECONDS', 86400)), 300)


def _active_key(user_id: int) -> str:
    return f'{INDIVIDUAL_SYNC_ACTIVE_PREFIX}{user_id}'


def _metadata_key(task_id: str) -> str:
    return f'{INDIVIDUAL_SYNC_METADATA_PREFIX}{task_id}'


def _dismissed_key(*, task_id: str, user_id: int) -> str:
    return f'{INDIVIDUAL_SYNC_DISMISSED_PREFIX}{user_id}:{task_id}'


def register_individual_sync_task(*, task_id: str, user_id: int, metadata: dict[str, Any]) -> None:
    client = _redis_client()
    pipe = client.pipeline()
    pipe.sadd(_active_key(user_id), task_id)
    pipe.expire(_active_key(user_id), _result_ttl_seconds())
    pipe.set(_metadata_key(task_id), json.dumps(metadata, separators=(',', ':')), ex=_result_ttl_seconds())
    pipe.execute()


def store_individual_sync_metadata(*, task_id: str, metadata: dict[str, Any]) -> None:
    _redis_client().set(
        _metadata_key(task_id),
        json.dumps(metadata, separators=(',', ':')),
        ex=_result_ttl_seconds(),
    )


def get_individual_sync_metadata(task_id: str) -> dict[str, Any]:
    raw = _redis_client().get(_metadata_key(task_id))
    if not raw:
        return {}
    try:
        value = json.loads(cast(str | bytes | bytearray, raw))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def get_tracked_individual_sync_task_ids(user_id: int) -> list[str]:
    jobs = (
        JobExecution.query.join(JobExecutionSubscriber, JobExecutionSubscriber.job_execution_id == JobExecution.id)
        .filter(
            JobExecutionSubscriber.user_id == user_id,
            JobExecution.operation == 'inventory_sync_cluster',
            JobExecution.status.in_((*ACTIVE_JOB_STATUSES, 'succeeded', 'partially_succeeded', 'failed')),
        )
        .order_by(JobExecution.created_at.desc())
        .limit(20)
        .all()
    )
    task_ids = {str(job.celery_task_id) for job in jobs if job.celery_task_id}
    try:
        task_ids.update(cast(set[str], _redis_client().smembers(_active_key(user_id))))
    except Exception:
        pass
    return sorted(task_ids)


def dismiss_individual_sync_result(*, task_id: str, user_id: int) -> None:
    client = _redis_client()
    pipe = client.pipeline()
    pipe.set(_dismissed_key(task_id=task_id, user_id=user_id), '1', ex=_result_ttl_seconds())
    pipe.srem(_active_key(user_id), task_id)
    pipe.execute()


def is_individual_sync_result_dismissed(*, task_id: str, user_id: int) -> bool:
    return bool(_redis_client().exists(_dismissed_key(task_id=task_id, user_id=user_id)))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _elapsed_seconds(payload: dict[str, Any]) -> int:
    started_value = payload.get('started_at') or payload.get('created_at')
    if not isinstance(started_value, str):
        return 0
    try:
        started = datetime.fromisoformat(started_value)
    except ValueError:
        return 0
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    finished_value = payload.get('finished_at')
    try:
        finished = datetime.fromisoformat(finished_value) if isinstance(finished_value, str) else datetime.now(UTC)
    except ValueError:
        finished = datetime.now(UTC)
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    return max(int((finished - started).total_seconds()), 0)


def build_individual_sync_snapshot(task_id: str) -> dict[str, Any]:
    result: AsyncResult = current_app.extensions['celery'].AsyncResult(task_id)
    try:
        payload = get_individual_sync_metadata(task_id)
    except Exception:
        payload = {}
    job = JobExecution.query.filter_by(celery_task_id=task_id).first()
    if job is not None:
        progress_metadata = (job.payload_json or {}).get('_progress')
        progress_metadata = progress_metadata if isinstance(progress_metadata, dict) else {}
        payload.setdefault('created_at', job.queued_at.isoformat() if job.queued_at else None)
        payload.setdefault('started_at', job.started_at.isoformat() if job.started_at else None)
        payload.setdefault('finished_at', job.completed_at.isoformat() if job.completed_at else None)
        payload.setdefault('requested_by_user_id', job.requested_by_user_id)
        payload.setdefault('cluster_id', job.scope_key)
        payload.setdefault('message', job.progress_message)
        payload.setdefault('progress_percent', progress_metadata.get('percent'))
        payload.setdefault('progress_stage', progress_metadata.get('stage'))
        payload.setdefault('progress_target', progress_metadata.get('target'))
        if job.result_summary_json:
            for key, value in job.result_summary_json.items():
                payload.setdefault(key, value)
    if isinstance(result.info, dict):
        payload.update(result.info)
    if result.state == 'SUCCESS' and isinstance(result.result, dict):
        payload.update(result.result)
    if result.state == 'FAILURE':
        payload.setdefault('status', 'error')
        payload.setdefault('title', 'Cluster inventory sync interrupted')
        payload.setdefault('message', 'The background worker could not complete the cluster inventory sync.')
        payload.setdefault('detail', 'Review the Celery worker and application logs before retrying.')
    state = result.state
    if job is not None:
        state = {
            'queued': 'PENDING',
            'running': 'PROGRESS',
            'retrying': 'RETRY',
            'cancel_requested': 'PROGRESS',
            'succeeded': 'SUCCESS',
            'partially_succeeded': 'SUCCESS',
            'failed': 'FAILURE',
            'canceled': 'REVOKED',
            'expired': 'REVOKED',
        }.get(job.status, state)
    return {
        'task_id': task_id,
        'celery_state': state,
        'state_label': state.lower().replace('_', ' '),
        'is_active': state in ACTIVE_CELERY_STATES,
        'status': payload.get('status', 'info'),
        'title': payload.get('title') or 'Cluster inventory sync in progress',
        'message': payload.get('message')
        or f'Synchronizing Kubernetes inventory for {payload.get("cluster_name", "the selected cluster")}.',
        'detail': payload.get('detail'),
        'cluster_id': payload.get('cluster_id'),
        'cluster_name': payload.get('cluster_name'),
        'requested_by_user_id': payload.get('requested_by_user_id'),
        'created_at': payload.get('created_at'),
        'started_at': payload.get('started_at'),
        'finished_at': payload.get('finished_at'),
        'duration_seconds': payload.get('duration_seconds'),
        'elapsed_seconds': _elapsed_seconds(payload),
        'progress_percent': max(0, min(_safe_int(payload.get('progress_percent')), 100)),
        'progress_stage': payload.get('progress_stage'),
        'progress_target': payload.get('progress_target'),
    }
