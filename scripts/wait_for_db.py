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



def _runtime_database_admitted(database_url: str) -> bool:
    """Fail closed until DevContainer app identity and immutable ledger ACLs are ready."""
    if os.getenv('APP_ENV') != 'development':
        return True  # server deployment has separate guarded admission authority
    with psycopg2.connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    current_user = 'kaori_runtime',
                    NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                         OR r.rolreplication OR r.rolbypassrls),
                    NOT pg_has_role('kaori_runtime', 'kaori_migrator', 'MEMBER'),
                    NOT has_schema_privilege(current_user, 'public', 'CREATE'),
                    has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'SELECT'),
                    has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'INSERT'),
                    NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'UPDATE'),
                    NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'DELETE'),
                    NOT has_table_privilege(current_user, 'public.capsule_handoff_ledger_events', 'TRUNCATE'),
                    (
                        SELECT count(*) = 4
                        FROM pg_trigger t
                        WHERE t.tgrelid = 'public.capsule_handoff_ledger_events'::regclass
                          AND t.tgname IN (
                              'tr_capsule_ledger_guard_insert',
                              'tr_capsule_ledger_deny_update',
                              'tr_capsule_ledger_deny_delete',
                              'tr_capsule_ledger_deny_truncate'
                          )
                          AND t.tgenabled IN ('O', 'A')
                    )
                FROM pg_roles r WHERE r.rolname = current_user
            """)
            result = cursor.fetchone()
            return bool(result and all(result))



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
        except psycopg2.Error:
            current_heads = frozenset()

        if current_heads == expected_heads:
            try:
                if _runtime_database_admitted(database_url):
                    print(f'Database schema and restricted runtime ready at head(s): {", ".join(sorted(expected_heads))}')
                    return
            except psycopg2.Error:
                pass  # grants/immutable ledger are not yet ready: keep workers gated

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
