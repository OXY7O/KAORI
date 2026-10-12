from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg2 import OperationalError

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / 'migrations'


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_bool(name: str) -> bool:
    return (os.getenv(name) or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _database_url() -> str:
    database_url = (os.getenv('DATABASE_URL') or '').strip()
    if not database_url:
        raise RuntimeError('DATABASE_URL is required before waiting for PostgreSQL')
    return database_url


def _expected_migration_heads() -> frozenset[str]:
    config = Config(str(MIGRATIONS_DIR / 'alembic.ini'))
    config.set_main_option('script_location', str(MIGRATIONS_DIR))
    heads = frozenset(ScriptDirectory.from_config(config).get_heads())
    if not heads:
        raise RuntimeError('No Alembic migration head is available for KAORI')
    return heads


def _current_migration_heads(database_url: str) -> frozenset[str]:
    connection = psycopg2.connect(database_url, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.alembic_version')")
            if cursor.fetchone()[0] is None:
                return frozenset()

            cursor.execute('SELECT version_num FROM alembic_version')
            return frozenset(row[0] for row in cursor.fetchall())
    finally:
        connection.close()



def _restricted_runtime_grants_ready(database_url: str) -> bool:
    """DevContainer-only gate: do not consume jobs before owner grant refresh.

    This is a read-only preliminary admission check, not a substitute for
    Capsule's authoritative PostgreSQL ledger/trigger/WAL START guard.
    """
    connection = psycopg2.connect(database_url, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    has_table_privilege(current_user, c.oid, 'SELECT'),
                    has_table_privilege(current_user, c.oid, 'INSERT'),
                    has_table_privilege(current_user, c.oid, 'UPDATE'),
                    has_table_privilege(current_user, c.oid, 'DELETE'),
                    has_table_privilege(current_user, c.oid, 'TRUNCATE'),
                    has_schema_privilege(current_user, 'public', 'CREATE'),
                    (SELECT rolsuper OR rolcreatedb OR rolcreaterole
                     FROM pg_roles WHERE rolname = current_user),
                    pg_get_userbyid(c.relowner) = current_user,
                    pg_has_role(
                        (SELECT oid FROM pg_roles WHERE rolname = current_user),
                        c.relowner, 'MEMBER'
                    )
                FROM pg_class AS c
                WHERE c.oid = to_regclass('public.capsule_handoff_ledger_events')
                """
            )
            return cursor.fetchone() == (
                True, True, False, False, False, False, False, False, False
            )
    finally:
        connection.close()



def wait_for_database() -> None:
    database_url = _database_url()
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


def wait_for_schema() -> None:
    database_url = _database_url()
    expected_heads = _expected_migration_heads()
    interval_seconds = max(_env_int('DB_WAIT_INTERVAL_SECONDS', 2), 1)
    announced = False

    while True:
        try:
            current_heads = _current_migration_heads(database_url)
        except OperationalError:
            current_heads = frozenset()

        if current_heads == expected_heads:
            if _env_bool('WAIT_FOR_RUNTIME_GRANTS'):
                try:
                    grants_ready = _restricted_runtime_grants_ready(database_url)
                except psycopg2.Error:
                    grants_ready = False
                if not grants_ready:
                    if not announced:
                        print('Schema migrated; waiting for restricted runtime ledger grants...')
                        announced = True
                    time.sleep(interval_seconds)
                    continue
            print(f'Database schema ready at migration head(s): {", ".join(sorted(expected_heads))}')
            return

        if not announced:
            current_label = ', '.join(sorted(current_heads)) or 'uninitialized'
            expected_label = ', '.join(sorted(expected_heads))
            print(
                'Database reachable; waiting for KAORI migration schema '
                f'(current: {current_label}; expected: {expected_label})...'
            )
            announced = True

        time.sleep(interval_seconds)


if __name__ == '__main__':
    try:
        wait_for_database()
        if _env_bool('WAIT_FOR_SCHEMA'):
            wait_for_schema()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
