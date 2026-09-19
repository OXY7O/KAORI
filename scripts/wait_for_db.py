from __future__ import annotations

import os
import sys
import time

import psycopg2
from psycopg2 import OperationalError


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def wait_for_database() -> None:
    database_url = (os.getenv('DATABASE_URL') or '').strip()
    if not database_url:
        raise RuntimeError('DATABASE_URL is required before waiting for PostgreSQL')

    attempts = max(_env_int('DB_WAIT_ATTEMPTS', 30), 1)
    interval_seconds = max(_env_int('DB_WAIT_INTERVAL_SECONDS', 2), 1)
    last_error: OperationalError | None = None

    for attempt in range(1, attempts + 1):
        try:
            connection = psycopg2.connect(database_url, connect_timeout=5)
            connection.close()
            print('Database ready')
            return
        except OperationalError as exc:
            last_error = exc
            print(f'Waiting for database ({attempt}/{attempts})...')
            if attempt < attempts:
                time.sleep(interval_seconds)

    raise RuntimeError(f'Database did not become ready after {attempts} attempts: {last_error}')


if __name__ == '__main__':
    try:
        wait_for_database()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
