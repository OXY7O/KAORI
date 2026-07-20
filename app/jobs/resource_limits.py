from __future__ import annotations

from flask import current_app
from redis import Redis

_RESOURCE_PREFIX = 'kaori:jobs:resource-slot:'

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local expires = tonumber(ARGV[2])
local member = ARGV[3]
local limit = tonumber(ARGV[4])
redis.call('zremrangebyscore', key, '-inf', now)
if redis.call('zscore', key, member) then
    redis.call('expire', key, tonumber(ARGV[5]))
    return 1
end
if redis.call('zcard', key) >= limit then
    return 0
end
redis.call('zadd', key, expires, member)
redis.call('expire', key, tonumber(ARGV[5]))
return 1
"""

_RELEASE_SCRIPT = """
local removed = redis.call('zrem', KEYS[1], ARGV[1])
if redis.call('zcard', KEYS[1]) == 0 then
    redis.call('del', KEYS[1])
end
return removed
"""


def _client() -> Redis:
    redis_url = current_app.config.get('REDIS_URL')
    if not redis_url:
        raise RuntimeError('REDIS_URL is required for distributed job resource limits.')
    return Redis.from_url(redis_url, decode_responses=True)


def _key(resource_group: str) -> str:
    return f'{_RESOURCE_PREFIX}{resource_group}'


def acquire_resource_slot(
    *,
    resource_group: str,
    task_id: str,
    limit: int,
    ttl_seconds: int,
    now_epoch: int,
) -> bool:
    selected_limit = max(int(limit), 1)
    selected_ttl = max(int(ttl_seconds), 60)
    return bool(
        _client().eval(
            _ACQUIRE_SCRIPT,
            1,
            _key(resource_group),
            int(now_epoch),
            int(now_epoch) + selected_ttl,
            task_id,
            selected_limit,
            selected_ttl,
        )
    )


def release_resource_slot(*, resource_group: str, task_id: str) -> bool:
    return bool(_client().eval(_RELEASE_SCRIPT, 1, _key(resource_group), task_id))
