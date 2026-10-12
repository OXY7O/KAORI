"""DevContainer-only, first-boot non-owner role admission (#1427).

This runs as a one-shot Compose dependency after the bundled PostgreSQL service
is healthy. It NEVER runs Alembic, seeds RBAC, modifies existing role passwords,
or writes credentials to a file. Production/external DBA lifecycle is separate.
"""
from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

_RUNTIME_NAME = 'kaori_runtime'
_DATABASE_NAME = 'kaori'
_OWNER_NAME = 'kaori'
_HOST = 'db'


def _abort(message: str) -> None:
    raise RuntimeError(f'DevContainer runtime bootstrap refused: {message}')


def main() -> int:
    if os.getenv('APP_ENV') != 'development':
        _abort('APP_ENV must be development')
    if os.getenv('KAORI_DB_MIGRATION_URL'):
        _abort('migration authority must not be passed to bootstrap service')
    runtime_raw = os.getenv('DATABASE_URL', '')
    if not runtime_raw:
        _abort('canonical DATABASE_URL is required')
    runtime = make_url(runtime_raw)
    if (
        runtime.drivername not in {'postgresql', 'postgresql+psycopg2'}
        or runtime.username != _RUNTIME_NAME
        or runtime.host != _HOST
        or (runtime.port or 5432) != 5432
        or runtime.database != _DATABASE_NAME
        or not runtime.password
    ):
        _abort('expected local restricted PostgreSQL URL (no credentials printed)')
    owner_name = os.getenv('POSTGRES_USER')
    owner_database = os.getenv('POSTGRES_DB')
    owner_secret = os.getenv('POSTGRES_PASSWORD')
    if owner_name != _OWNER_NAME or owner_database != _DATABASE_NAME or not owner_secret:
        _abort('bundled PostgreSQL owner configuration differs from kaori-dev')
    if runtime.password == owner_secret:
        _abort('runtime and owner secrets must differ')

    # Never print a SQL string containing the role password.
    with psycopg2.connect(
        host=_HOST, port=5432, dbname=owner_database,
        user=owner_name, password=owner_secret,
        application_name='kaori-dev-runtime-role-bootstrap',
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user, current_database()')
            actual_user, actual_database = cursor.fetchone()
            if actual_user != _OWNER_NAME or actual_database != _DATABASE_NAME:
                _abort('actual owner/database does not match local bootstrap authority')
            cursor.execute(
                """
                SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                       rolreplication, rolbypassrls
                FROM pg_roles WHERE rolname = %s
                """,
                (_RUNTIME_NAME,),
            )
            existing = cursor.fetchone()
            if existing is None:
                cursor.execute(
                    "SELECT to_regclass('public.alembic_version'), "
                    "to_regclass('public.users')"
                )
                if any(value is not None for value in cursor.fetchone()):
                    _abort('existing KAORI schema found without runtime role; use the data-preserving cutover')
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD {}"
                    ).format(sql.Identifier(_RUNTIME_NAME), sql.Literal(runtime.password))
                )
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(_DATABASE_NAME),
                        sql.Identifier(_RUNTIME_NAME),
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(_RUNTIME_NAME)
                    )
                )
            elif existing != (True, False, False, False, False, False):
                _abort('existing application role has elevated attributes or cannot log in')
            cursor.execute(
                "SELECT has_schema_privilege(%s, 'public', 'CREATE')",
                (_RUNTIME_NAME,),
            )
            if cursor.fetchone()[0]:
                _abort('application role unexpectedly has public schema CREATE')

    # A configured password mismatch must stop DevContainer readiness rather
    # than silently rotate an existing database principal on every reopen.
    try:
        with psycopg2.connect(runtime_raw, application_name='kaori-dev-runtime-login-check',
                              connect_timeout=5) as verify:
            with verify.cursor() as cursor:
                cursor.execute('SELECT current_user, current_database()')
                if cursor.fetchone() != (_RUNTIME_NAME, _DATABASE_NAME):
                    _abort('runtime connection resolved the wrong identity/database')
    except psycopg2.Error as exc:
        raise RuntimeError(
            'DevContainer runtime login failed; check private DATABASE_URL '
            'against the existing runtime role password'
        ) from None

    print('PASS: DevContainer restricted runtime role and login admitted')
    print('Schema migration remains explicitly owner-only; first-run UI is available.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
