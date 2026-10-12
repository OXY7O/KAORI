"""Provision three isolated identities for a fresh bundled DevContainer DB.

This one-shot job holds postgres/migrator Docker secrets, never passed to the
Flask workspace, Celery workers, or Beat. It creates principals and ownership
but DOES NOT execute migrations, create application tables, seed RBAC, or
create the first KAORI administrator. Existing databases are read-only checked.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

_DATABASE = 'kaori'
_MIGRATOR = 'kaori_migrator'
_RUNTIME = 'kaori_runtime'


def _abort(message: str) -> None:
    raise RuntimeError(f'DevContainer PostgreSQL bootstrap refused: {message}')


def _read_secret(name: str) -> str:
    filename = os.getenv(name, '')
    if not filename or not filename.startswith('/run/secrets/'):
        _abort(f'{name} must reference an explicitly mounted Docker secret')
    try:
        secret = Path(filename).read_text(encoding='utf-8').rstrip('\r\n')
    except OSError:
        _abort(f'cannot read {name} Docker secret')
    if not secret or len(secret) < 16:
        _abort(f'{name} must be a nonempty strong credential')
    return secret


def _role_flags(cursor: object, name: str) -> tuple[bool, ...] | None:
    cursor.execute(
        """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                  rolreplication, rolbypassrls
           FROM pg_roles WHERE rolname = %s""",
        (name,),
    )
    return cursor.fetchone()


def main() -> int:
    if os.getenv('APP_ENV') != 'development':
        _abort('APP_ENV must be development')
    if os.getenv('KAORI_DB_MIGRATION_URL'):
        _abort('migration URL is forbidden in the one-shot bootstrap job')
    url = make_url(os.getenv('DATABASE_URL', ''))
    if (
        url.drivername not in {'postgresql', 'postgresql+psycopg2'}
        or url.username != _RUNTIME
        or url.host != 'db'
        or (url.port or 5432) != 5432
        or url.database != _DATABASE
        or not url.password
    ):
        _abort('expected local kaori_runtime DATABASE_URL (no credentials logged)')

    admin_password = _read_secret('KAORI_DB_BOOTSTRAP_PASSWORD_FILE')
    migrator_password = _read_secret('KAORI_DB_MIGRATOR_PASSWORD_FILE')
    if len({admin_password, migrator_password, url.password}) != 3:
        _abort('postgres, kaori_migrator and kaori_runtime must have different secrets')

    # Abort on pre-existing schema without a fully provisioned identity set;
    # never adopt or mutate arbitrary databases in a first-install job.
    with psycopg2.connect(
        host='db', port=5432, dbname=_DATABASE, user='postgres',
        password=admin_password, connect_timeout=5,
        application_name='kaori-dev-three-role-first-boot',
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user, current_database(), pg_is_in_recovery()')
            if cursor.fetchone() != ('postgres', _DATABASE, False):
                _abort('wrong database/bootstrap identity or recovery replica')
            cursor.execute(
                "SELECT to_regclass('public.alembic_version'), to_regclass('public.users')"
            )
            schema_objects = cursor.fetchone()
            migrator = _role_flags(cursor, _MIGRATOR)
            runtime = _role_flags(cursor, _RUNTIME)
            if (migrator is None) != (runtime is None):
                _abort('incomplete pre-existing role provisioning; manual review required')
            if migrator is None:
                if any(schema_objects):
                    _abort('existing schema needs the data-preserving migration/cutover procedure')
                for name, password in ((_MIGRATOR, migrator_password), (_RUNTIME, url.password)):
                    cursor.execute(
                        sql.SQL(
                            'CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB '
                            'NOCREATEROLE NOREPLICATION NOBYPASSRLS INHERIT PASSWORD {}'
                        ).format(sql.Identifier(name), sql.Literal(password))
                    )
                cursor.execute('ALTER DATABASE kaori OWNER TO kaori_migrator')
                cursor.execute('ALTER SCHEMA public OWNER TO kaori_migrator')
                cursor.execute('REVOKE ALL PRIVILEGES ON DATABASE kaori FROM PUBLIC')
                cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                cursor.execute('GRANT CONNECT ON DATABASE kaori TO kaori_runtime')
                cursor.execute('GRANT USAGE ON SCHEMA public TO kaori_runtime')
            else:
                for role, flags in ((_MIGRATOR, migrator), (_RUNTIME, runtime)):
                    if flags != (True, False, False, False, False, False):
                        _abort(f'{role} is elevated or cannot log in')

            cursor.execute(
                """SELECT pg_get_userbyid(datdba) FROM pg_database
                   WHERE datname = %s""", (_DATABASE,),
            )
            if cursor.fetchone()[0] != _MIGRATOR:
                _abort('database owner differs from kaori_migrator')
            cursor.execute(
                """SELECT pg_get_userbyid(nspowner) FROM pg_namespace
                   WHERE nspname = 'public'"""
            )
            if cursor.fetchone()[0] != _MIGRATOR:
                _abort('public schema owner differs from kaori_migrator')
            cursor.execute(
                """SELECT
                    has_schema_privilege(%s, 'public', 'CREATE'),
                    has_schema_privilege(%s, 'public', 'CREATE'),
                    pg_has_role(%s, %s, 'MEMBER')""",
                (_MIGRATOR, _RUNTIME, _RUNTIME, _MIGRATOR),
            )
            if cursor.fetchone() != (True, False, False):
                _abort('invalid schema CREATE or inherited migrator privilege')

    # Validate both logins without ever rotating existing credentials.
    for role, password in ((_MIGRATOR, migrator_password), (_RUNTIME, url.password)):
        try:
            with psycopg2.connect(
                host='db', port=5432, dbname=_DATABASE, user=role,
                password=password, connect_timeout=5,
                application_name='kaori-dev-identity-admission',
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT current_user, current_database()')
                    if cursor.fetchone() != (role, _DATABASE):
                        _abort(f'{role} resolved unexpected effective identity/database')
        except psycopg2.Error:
            _abort(f'{role} login failed; inspect the external secrets and private DATABASE_URL')

    print('PASS: postgres bootstrap, kaori_migrator and kaori_runtime separated')
    print('Schema deliberately untouched; operator must run KAORI Initialize Fresh Database.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, psycopg2.Error) as exc:
        if isinstance(exc, psycopg2.Error):
            print('DevContainer PostgreSQL bootstrap failed (database error; secrets suppressed).', file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
