from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from flask import current_app
from redis import Redis

from app.jobs.constants import ACTIVE_JOB_STATUSES

logger = logging.getLogger(__name__)

ACTIVE_CELERY_STATES = {'PENDING', 'RECEIVED', 'STARTED', 'PROGRESS', 'RETRY'}
VALIDATION_LOCK_PREFIX = 'kaori:integration-validation:lock:'
VALIDATION_METADATA_PREFIX = 'kaori:integration-validation:metadata:'

_CLAIM_SCRIPT = """
for index = 1, #KEYS do
    if redis.call('exists', KEYS[index]) == 1 then
        return 0
    end
end
redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""

_COMPARE_DELETE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def _redis_client() -> Redis:
    redis_url = current_app.config.get('REDIS_URL')
    if not redis_url:
        raise RuntimeError('REDIS_URL is required for integration validation task tracking.')
    return Redis.from_url(redis_url, decode_responses=True)


def _result_ttl_seconds() -> int:
    return max(int(current_app.config.get('CELERY_RESULT_EXPIRES_SECONDS', 86400)), 300)


def _lock_ttl_seconds() -> int:
    return max(int(current_app.config.get('INTEGRATION_VALIDATION_LOCK_TTL_SECONDS', 7200)), 300)


def _target_key(
    *,
    provider_type: str,
    operation: str,
    instance_id: int | str,
    binding_id: int | str | None = None,
) -> str:
    target = f'{provider_type}:{operation}:{instance_id}'
    if binding_id is not None:
        target = f'{target}:{binding_id}'
    return target


def _lock_key(
    *,
    provider_type: str,
    operation: str,
    instance_id: int | str,
    binding_id: int | str | None = None,
) -> str:
    return f'{VALIDATION_LOCK_PREFIX}{_target_key(provider_type=provider_type, operation=operation, instance_id=instance_id, binding_id=binding_id)}'


def _metadata_key(task_id: str) -> str:
    return f'{VALIDATION_METADATA_PREFIX}{task_id}'


def _release_stale_validation_lock(client: Redis, key: str) -> bool:
    """Release a Redis lock only when its canonical job is no longer active.

    Redis is the fast cross-process mutex, while JobExecution is the durable
    lifecycle authority. A worker crash or interrupted dispatch can leave the
    mutex behind until its TTL expires even though the owning job has already
    reached a terminal state. The compare-delete keeps reclamation safe when
    another process changes the lock between inspection and deletion.
    """
    owner_task_id = client.get(key)
    if not owner_task_id:
        return False
    owner_task_id = str(owner_task_id)
    try:
        from app.jobs.service import get_job_by_task_id

        job = get_job_by_task_id(owner_task_id)
    except Exception:
        logger.exception('Could not verify validation lock owner %s for %s.', owner_task_id, key)
        return False
    if job is not None and str(job.status) in ACTIVE_JOB_STATUSES:
        return False
    released = client.eval(_COMPARE_DELETE_SCRIPT, 1, key, owner_task_id)
    if released:
        logger.warning(
            'Released stale integration validation lock %s owned by terminal or missing task %s.',
            key,
            owner_task_id,
        )
    return bool(released)


def claim_validation_job(
    *,
    task_id: str,
    provider_type: str,
    operation: str,
    instance_id: int | str,
    binding_id: int | str | None,
    metadata: dict[str, Any],
    conflicting_operations: tuple[str, ...] = (),
) -> bool:
    client = _redis_client()
    lock_key = _lock_key(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
    )
    conflict_keys = [
        _lock_key(
            provider_type=provider_type,
            operation=conflicting_operation,
            instance_id=instance_id,
            binding_id=None,
        )
        for conflicting_operation in conflicting_operations
        if conflicting_operation and conflicting_operation != operation
    ]
    for candidate_key in (lock_key, *conflict_keys):
        _release_stale_validation_lock(client, candidate_key)
    acquired = bool(
        client.eval(
            _CLAIM_SCRIPT,
            1 + len(conflict_keys),
            lock_key,
            *conflict_keys,
            task_id,
            _lock_ttl_seconds(),
        )
    )
    if not acquired:
        return False
    try:
        store_validation_metadata(task_id=task_id, metadata=metadata)
    except Exception:
        release_validation_job(
            task_id=task_id,
            provider_type=provider_type,
            operation=operation,
            instance_id=instance_id,
            binding_id=binding_id,
        )
        raise
    return True


def get_active_validation_task_id(
    *,
    provider_type: str,
    operation: str,
    instance_id: int | str,
    binding_id: int | str | None = None,
) -> str | None:
    from app.jobs.service import find_active_job

    scope_key = f'binding:{binding_id}' if binding_id is not None else None
    job = find_active_job(
        provider_type=provider_type,
        provider_instance_id=int(instance_id),
        operation=operation,
        scope_key=scope_key,
    )
    if job is None or not job.celery_task_id:
        return None
    return str(job.celery_task_id)


def release_validation_job(
    *,
    task_id: str,
    provider_type: str,
    operation: str,
    instance_id: int | str,
    binding_id: int | str | None = None,
) -> bool:
    key = _lock_key(
        provider_type=provider_type,
        operation=operation,
        instance_id=instance_id,
        binding_id=binding_id,
    )
    released = _redis_client().eval(_COMPARE_DELETE_SCRIPT, 1, key, task_id)
    return bool(released)


def store_validation_metadata(*, task_id: str, metadata: dict[str, Any]) -> None:
    _redis_client().set(
        _metadata_key(task_id),
        json.dumps(metadata, separators=(',', ':'), default=str),
        ex=_result_ttl_seconds(),
    )


def get_validation_metadata(task_id: str) -> dict[str, Any]:
    raw = _redis_client().get(_metadata_key(task_id))
    if not raw:
        return {}
    try:
        value = json.loads(cast(str | bytes | bytearray, raw))
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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


def build_validation_snapshot(task_id: str) -> dict[str, Any]:
    result = current_app.extensions['celery'].AsyncResult(task_id)
    payload = get_validation_metadata(task_id)
    canonical: dict[str, Any] = {}
    try:
        from app.jobs.service import get_job_by_task_id, job_snapshot

        job = get_job_by_task_id(task_id)
        if job is not None:
            canonical = job_snapshot(job)
            payload = {**canonical, **payload}
    except Exception:
        canonical = {}
    if isinstance(result.info, dict):
        payload.update(result.info)
    if result.state == 'SUCCESS' and isinstance(result.result, dict):
        payload.update(result.result)
    if result.state == 'FAILURE':
        payload.setdefault('status', 'error')
        payload.setdefault('title', 'Integration validation interrupted')
        payload.setdefault('message', 'The validation worker could not complete the requested operation.')
        payload.setdefault('detail', 'Review the validation-worker logs and Redis connectivity before retrying.')
    canonical_status = str(canonical.get('status') or '')
    canonical_active = bool(canonical.get('is_active'))
    canonical_complete = bool(canonical.get('is_complete'))
    state_label = canonical_status.replace('_', ' ') if canonical_status else result.state.lower().replace('_', ' ')
    return {
        **payload,
        'task_id': task_id,
        'celery_state': result.state,
        'state_label': state_label,
        'is_active': canonical_active if canonical else result.state in ACTIVE_CELERY_STATES,
        'is_complete': canonical_complete if canonical else result.state in {'SUCCESS', 'FAILURE', 'REVOKED'},
        'elapsed_seconds': _elapsed_seconds(payload),
        'feedback': payload.get('feedback'),
    }
