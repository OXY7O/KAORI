from __future__ import annotations

import pickle
from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from time import monotonic, sleep, time
from typing import Any
from uuid import uuid4

from flask import current_app, has_app_context
from redis import Redis
from redis.exceptions import RedisError

_CACHE: dict[str, tuple[float, float, Any]] = {}
_LOCK = RLock()
_PREFIX = 'kaori:analytics:cache:'
_ENVELOPE_MARKER = 'kaori-analytics-cache-v1'


def _redis_client() -> Redis | None:
    if not has_app_context():
        return None
    redis_url = current_app.config.get('REDIS_URL')
    if not redis_url:
        return None
    return Redis.from_url(str(redis_url), decode_responses=False)


def _stale_ttl(ttl_seconds: int) -> int:
    return max(ttl_seconds * 10, ttl_seconds + 300)


def _local_lookup(key: str) -> tuple[str, Any] | None:
    now = monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is None:
            return None
        fresh_until, stale_until, value = cached
        if stale_until <= now:
            _CACHE.pop(key, None)
            return None
        return ('fresh' if fresh_until > now else 'stale', deepcopy(value))


def _local_set(key: str, ttl_seconds: int, value: Any) -> None:
    now = monotonic()
    with _LOCK:
        _CACHE[key] = (
            now + max(ttl_seconds, 1),
            now + _stale_ttl(max(ttl_seconds, 1)),
            deepcopy(value),
        )


def _encode_redis_value(value: Any, ttl_seconds: int) -> bytes:
    envelope = {
        'marker': _ENVELOPE_MARKER,
        'expires_at': time() + max(ttl_seconds, 1),
        'value': value,
    }
    return pickle.dumps(envelope, protocol=5)


def _decode_redis_value(raw: bytes) -> tuple[str, Any]:
    decoded = pickle.loads(raw)
    if not isinstance(decoded, dict) or decoded.get('marker') != _ENVELOPE_MARKER:
        return 'fresh', decoded
    state = 'fresh' if float(decoded.get('expires_at') or 0) > time() else 'stale'
    return state, decoded.get('value')


def _wait_for_shared_value(client: Redis, cache_key: str, *, attempts: int = 300) -> Any | None:
    for _ in range(attempts):
        sleep(0.1)
        raw = client.get(cache_key)
        if raw is not None:
            _, value = _decode_redis_value(raw)
            return value
    return None


def get_or_set_cache[T](
    key: str,
    ttl_seconds: int,
    loader: Callable[[], T],
) -> T:
    """Use one Redis-backed cache and stampede lock across every web replica.

    Fresh values are shared across processes. Expired values remain available for
    a bounded stale window while one caller refreshes them, so concurrent users
    do not fan out the same Prometheus query.
    """
    local = _local_lookup(key)
    if local is not None and local[0] == 'fresh':
        return local[1]
    stale_value = local[1] if local is not None else None

    client = _redis_client()
    cache_key = f'{_PREFIX}{key}'
    lock_key = f'{cache_key}:lock'
    if client is not None:
        try:
            raw = client.get(cache_key)
            if raw is not None:
                state, value = _decode_redis_value(raw)
                if state == 'fresh':
                    _local_set(key, ttl_seconds, value)
                    return deepcopy(value)
                stale_value = value

            lock_token = str(uuid4()).encode()
            acquired = bool(client.set(lock_key, lock_token, nx=True, ex=180))
            if not acquired:
                if stale_value is not None:
                    return deepcopy(stale_value)
                shared_value = _wait_for_shared_value(client, cache_key)
                if shared_value is not None:
                    _local_set(key, ttl_seconds, shared_value)
                    return deepcopy(shared_value)
            else:
                try:
                    value = loader()
                    client.setex(
                        cache_key,
                        _stale_ttl(max(ttl_seconds, 1)),
                        _encode_redis_value(value, ttl_seconds),
                    )
                    _local_set(key, ttl_seconds, value)
                    return value
                finally:
                    current = client.get(lock_key)
                    if current == lock_token:
                        client.delete(lock_key)
        except (RedisError, pickle.PickleError, EOFError, AttributeError, ValueError, TypeError):
            if has_app_context():
                current_app.logger.exception('Analytics shared cache failed for key %s.', key)

    if stale_value is not None:
        return deepcopy(stale_value)
    value = loader()
    _local_set(key, ttl_seconds, value)
    return value


def forget_cache_prefix(prefix: str) -> None:
    with _LOCK:
        for key in list(_CACHE):
            if key.startswith(prefix):
                _CACHE.pop(key, None)

    client = _redis_client()
    if client is None:
        return
    try:
        pattern = f'{_PREFIX}{prefix}*'
        for raw_key in client.scan_iter(match=pattern, count=100):
            client.delete(raw_key)
    except RedisError:
        if has_app_context():
            current_app.logger.exception('Could not clear analytics cache prefix %s.', prefix)
