from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Any

_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = RLock()


def get_or_set_cache[T](
    key: str,
    ttl_seconds: int,
    loader: Callable[[], T],
) -> T:
    now = monotonic()

    with _LOCK:
        cached = _CACHE.get(key)
        if cached:
            expires_at, value = cached
            if expires_at > now:
                return deepcopy(value)

    value = loader()

    with _LOCK:
        _CACHE[key] = (now + max(ttl_seconds, 1), deepcopy(value))

    return value


def forget_cache_prefix(prefix: str) -> None:
    with _LOCK:
        for key in list(_CACHE):
            if key.startswith(prefix):
                _CACHE.pop(key, None)
