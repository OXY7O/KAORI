from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Iterator

from sqlalchemy import text

from app.extensions import db


class RetentionLockUnavailable(RuntimeError):
    pass


_fallback_locks: dict[str, Lock] = {}


@contextmanager
def retention_lock(domain: str) -> Iterator[None]:
    lock_key = f'kaori:retention:{domain}'
    engine = db.engine

    if engine.dialect.name == 'postgresql':
        connection = engine.connect()
        acquired = bool(
            connection.execute(
                text('SELECT pg_try_advisory_lock(hashtext(:lock_key))'),
                {'lock_key': lock_key},
            ).scalar()
        )
        if not acquired:
            connection.close()
            raise RetentionLockUnavailable(f'A retention job is already running for {domain}.')

        try:
            yield
        finally:
            try:
                connection.execute(
                    text('SELECT pg_advisory_unlock(hashtext(:lock_key))'),
                    {'lock_key': lock_key},
                )
            finally:
                connection.close()
        return

    fallback_lock = _fallback_locks.setdefault(lock_key, Lock())
    if not fallback_lock.acquire(blocking=False):
        raise RetentionLockUnavailable(f'A retention job is already running for {domain}.')
    try:
        yield
    finally:
        fallback_lock.release()
