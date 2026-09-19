from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from celery.result import AsyncResult
from flask import current_app
from redis import Redis

from app.common.job_execution_contract import KUBERNETES_INVENTORY_SYNC_OPERATION
from app.models.job import JobExecution
from app.platform_operations.jobs.constants import ACTIVE_JOB_STATUSES

CLUSTER_SYNC_TASK_NAME = 'app.kubernetes.cluster.tasks.sync_all_clusters'
CLUSTER_SYNC_QUEUE = 'inventory'
CLUSTER_SYNC_LOCK_KEY = 'kaori:cluster-sync:lock'
CLUSTER_SYNC_METADATA_PREFIX = 'kaori:cluster-sync:metadata:'
CLUSTER_SYNC_DISMISSED_PREFIX = 'kaori:cluster-sync:dismissed:'
ACTIVE_CELERY_STATES = {
    'PENDING',
    'RECEIVED',
    'STARTED',
    'PROGRESS',
    'RETRY',
}

_COMPARE_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

_COMPARE_EXPIRE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


def _redis_client() -> Redis:
    redis_url = current_app.config.get('REDIS_URL')

    if not redis_url:
        raise RuntimeError('REDIS_URL is required for persistent cluster synchronization.')

    return Redis.from_url(
        redis_url,
        decode_responses=True,
    )


def _metadata_key(task_id: str) -> str:
    return f'{CLUSTER_SYNC_METADATA_PREFIX}{task_id}'


def _dismissed_key(
    *,
    task_id: str,
    user_id: int,
) -> str:
    return f'{CLUSTER_SYNC_DISMISSED_PREFIX}{user_id}:{task_id}'


def _result_ttl_seconds() -> int:
    return max(
        int(current_app.config.get('CELERY_RESULT_EXPIRES_SECONDS', 86400)),
        300,
    )


def _lock_ttl_seconds() -> int:
    return max(
        int(current_app.config.get('CLUSTER_SYNC_LOCK_TTL_SECONDS', 10800)),
        300,
    )


def _completed_ttl_seconds() -> int:
    return max(
        int(current_app.config.get('CLUSTER_SYNC_COMPLETED_TTL_SECONDS', 300)),
        30,
    )


def acquire_cluster_sync_lock(
    *,
    task_id: str,
    metadata: dict[str, Any],
) -> bool:
    redis_client = _redis_client()
    acquired = bool(
        redis_client.set(
            CLUSTER_SYNC_LOCK_KEY,
            task_id,
            nx=True,
            ex=_lock_ttl_seconds(),
        )
    )

    if not acquired:
        return False

    try:
        store_cluster_sync_metadata(
            task_id=task_id,
            metadata=metadata,
        )
    except Exception:
        release_cluster_sync_lock(
            task_id,
        )
        raise

    return True


def get_active_cluster_sync_task_id() -> str | None:
    job = (
        JobExecution.query.filter(
            JobExecution.operation == KUBERNETES_INVENTORY_SYNC_OPERATION,
            JobExecution.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(JobExecution.created_at.desc())
        .first()
    )
    if job is not None and job.celery_task_id:
        return str(job.celery_task_id)
    try:
        task_id = _redis_client().get(CLUSTER_SYNC_LOCK_KEY)
    except Exception:
        return None
    return cast(str | None, task_id) or None


def claim_cluster_sync_lock(task_id: str) -> bool:
    redis_client = _redis_client()
    current_task_id = redis_client.get(
        CLUSTER_SYNC_LOCK_KEY,
    )

    if current_task_id == task_id:
        return refresh_cluster_sync_lock(
            task_id,
        )

    if current_task_id:
        return False

    return bool(
        redis_client.set(
            CLUSTER_SYNC_LOCK_KEY,
            task_id,
            nx=True,
            ex=_lock_ttl_seconds(),
        )
    )


def refresh_cluster_sync_lock(task_id: str) -> bool:
    return bool(
        _redis_client().eval(
            _COMPARE_EXPIRE_SCRIPT,
            1,
            CLUSTER_SYNC_LOCK_KEY,
            task_id,
            str(_lock_ttl_seconds()),
        )
    )


def mark_cluster_sync_completed(task_id: str) -> bool:
    return bool(
        _redis_client().eval(
            _COMPARE_EXPIRE_SCRIPT,
            1,
            CLUSTER_SYNC_LOCK_KEY,
            task_id,
            str(_completed_ttl_seconds()),
        )
    )


def release_cluster_sync_lock(task_id: str) -> bool:
    return bool(
        _redis_client().eval(
            _COMPARE_DELETE_SCRIPT,
            1,
            CLUSTER_SYNC_LOCK_KEY,
            task_id,
        )
    )


def store_cluster_sync_metadata(
    *,
    task_id: str,
    metadata: dict[str, Any],
) -> None:
    _redis_client().set(
        _metadata_key(task_id),
        json.dumps(
            metadata,
            separators=(',', ':'),
        ),
        ex=_result_ttl_seconds(),
    )


def get_cluster_sync_metadata(task_id: str) -> dict[str, Any]:
    raw_metadata = _redis_client().get(
        _metadata_key(task_id),
    )

    if not raw_metadata:
        return {}

    try:
        parsed = json.loads(
            cast(str | bytes | bytearray, raw_metadata),
        )
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def dismiss_cluster_sync_result(
    *,
    task_id: str,
    user_id: int,
) -> None:
    _redis_client().set(
        _dismissed_key(
            task_id=task_id,
            user_id=user_id,
        ),
        '1',
        ex=_result_ttl_seconds(),
    )


def is_cluster_sync_result_dismissed(
    *,
    task_id: str,
    user_id: int,
) -> bool:
    return bool(
        _redis_client().exists(
            _dismissed_key(
                task_id=task_id,
                user_id=user_id,
            )
        )
    )


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _elapsed_seconds(payload: dict[str, Any]) -> int:
    started_at = payload.get('started_at') or payload.get('created_at')

    if not isinstance(started_at, str) or not started_at:
        return 0

    try:
        started = datetime.fromisoformat(
            started_at,
        )
    except ValueError:
        return 0

    if started.tzinfo is None:
        started = started.replace(
            tzinfo=UTC,
        )

    finished_at = payload.get('finished_at')
    finished: datetime | None = None

    if isinstance(finished_at, str) and finished_at:
        try:
            finished = datetime.fromisoformat(
                finished_at,
            )
        except ValueError:
            finished = None

    if finished is None:
        finished = datetime.now(
            UTC,
        )
    elif finished.tzinfo is None:
        finished = finished.replace(
            tzinfo=UTC,
        )

    return max(
        int((finished - started).total_seconds()),
        0,
    )


def build_cluster_sync_snapshot(task_id: str) -> dict[str, Any]:
    celery_app = current_app.extensions['celery']
    async_result: AsyncResult = celery_app.AsyncResult(
        task_id,
    )
    state = str(async_result.state or 'PENDING').upper()
    job = JobExecution.query.filter_by(celery_task_id=task_id).first()
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
    try:
        payload = get_cluster_sync_metadata(task_id)
    except Exception:
        payload = {}
    job = JobExecution.query.filter_by(celery_task_id=task_id).first()
    if job is not None:
        progress_metadata = (job.payload_json or {}).get('_progress')
        progress_metadata = progress_metadata if isinstance(progress_metadata, dict) else {}
        payload.setdefault('progress_percent', progress_metadata.get('percent'))
        payload.setdefault('progress_stage', progress_metadata.get('stage'))
        payload.setdefault('progress_target', progress_metadata.get('target'))
        payload.setdefault('created_at', job.queued_at.isoformat() if job.queued_at else None)
        payload.setdefault('started_at', job.started_at.isoformat() if job.started_at else None)
        payload.setdefault('finished_at', job.completed_at.isoformat() if job.completed_at else None)
        payload.setdefault('requested_by_user_id', job.requested_by_user_id)
        payload['processed_count'] = max(int(job.progress_current or 0), int(payload.get('processed_count') or 0))
        payload['total_count'] = max(int(job.progress_total or 0), int(payload.get('total_count') or 0))
        payload.setdefault('message', job.progress_message)
        if job.result_summary_json:
            for key, value in job.result_summary_json.items():
                payload.setdefault(key, value)

    info = async_result.info
    if isinstance(info, dict):
        payload.update(
            info,
        )

    if state == 'SUCCESS' and isinstance(async_result.result, dict):
        payload.update(
            async_result.result,
        )

    total_count = max(
        _safe_int(payload.get('total_count')),
        0,
    )
    processed_count = min(
        max(
            _safe_int(payload.get('processed_count')),
            0,
        ),
        total_count,
    )
    synced_count = max(
        _safe_int(payload.get('synced_count')),
        0,
    )
    failed_count = max(
        _safe_int(payload.get('failed_count')),
        0,
    )

    reported_progress_percent = max(_safe_int(payload.get('progress_percent')), 0)
    progress_percent = 0
    if reported_progress_percent:
        progress_percent = min(reported_progress_percent, 100)
    elif total_count > 0:
        progress_percent = min(
            int((processed_count / total_count) * 100),
            100,
        )

    is_active = state in ACTIVE_CELERY_STATES

    if state == 'FAILURE':
        payload.setdefault(
            'status',
            'error',
        )
        payload.setdefault(
            'title',
            'Kubernetes sync interrupted',
        )
        payload.setdefault(
            'message',
            'The Celery worker could not complete the cluster synchronization task.',
        )
        payload.setdefault(
            'detail',
            str(async_result.result) or 'Review the Celery worker logs before retrying.',
        )
    elif state == 'REVOKED':
        payload.setdefault(
            'status',
            'warning',
        )
        payload.setdefault(
            'title',
            'Kubernetes sync cancelled',
        )
        payload.setdefault(
            'message',
            'The background synchronization task was revoked before completion.',
        )
        payload.setdefault(
            'detail',
            'Start a new synchronization after confirming the Celery worker is healthy.',
        )

    return {
        'task_id': task_id,
        'celery_state': state,
        'state_label': state.lower().replace('_', ' '),
        'is_active': is_active,
        'status': payload.get('status', 'info'),
        'title': payload.get('title'),
        'message': payload.get('message'),
        'detail': payload.get('detail'),
        'total_count': total_count,
        'processed_count': processed_count,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'current_cluster_name': payload.get('current_cluster_name'),
        'failed_clusters': payload.get('failed_clusters') or [],
        'duration_seconds': payload.get('duration_seconds'),
        'elapsed_seconds': _elapsed_seconds(payload),
        'progress_percent': progress_percent,
        'progress_stage': payload.get('progress_stage'),
        'progress_target': payload.get('progress_target'),
        'requested_by_user_id': payload.get('requested_by_user_id'),
        'created_at': payload.get('created_at'),
        'started_at': payload.get('started_at'),
        'finished_at': payload.get('finished_at'),
    }
