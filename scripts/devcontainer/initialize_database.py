"""Explicit, operator-run DevContainer migration with a separate DDL identity.

The migrator password is requested at an interactive terminal. It is NEVER
stored in the workspace .env, mounted as a runtime secret, or given to workers.
The postgres bootstrap identity is not used for Alembic or app RBAC.
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys

import psycopg2
from sqlalchemy.engine import URL, make_url


def _abort(message: str) -> None:
    raise RuntimeError(f'DevContainer database initialization refused: {message}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Upgrade the local KAORI schema as kaori_migrator')
    parser.add_argument(
        '--bootstrap-admin', action='store_true',
        help='After migration and grants, initialize the first application admin as kaori_runtime',
    )
    args = parser.parse_args()

    if os.getenv('APP_ENV') != 'development':
        _abort('only the local development runtime is authorized')
    if os.getenv('KAORI_DB_MIGRATION_URL') or os.getenv('KAORI_DB_MIGRATION_PASSWORD'):
        _abort('remove ambient migration credentials; use the protected interactive prompt')
    runtime_raw = os.getenv('DATABASE_URL', '')
    runtime = make_url(runtime_raw)
    if (
        runtime.drivername not in {'postgresql', 'postgresql+psycopg2'}
        or runtime.username != 'kaori_runtime'
        or runtime.host != 'db'
        or (runtime.port or 5432) != 5432
        or runtime.database != 'kaori'
        or not runtime.password
    ):
        _abort('DATABASE_URL must identify the isolated local runtime principal')

    # Refuse incomplete first-admin credentials BEFORE writing any schema.
    if args.bootstrap_admin:
        username = (os.getenv('ADMIN_USERNAME') or '').strip()
        email = (os.getenv('ADMIN_EMAIL') or '').strip()
        password = os.getenv('ADMIN_PASSWORD') or ''
        key = os.getenv('INTEGRATION_CREDENTIAL_KEY') or ''
        if (
            not username or not email or '@' not in email
            or len(password) < 12 or 'replace-with' in password.lower()
            or not key or 'replace-with' in key.lower()
        ):
            _abort('configure private ADMIN_* and INTEGRATION_CREDENTIAL_KEY before migration')

    if not sys.stdin.isatty():
        _abort('an interactive terminal is required for the migration secret')
    migrator_password = getpass.getpass('PostgreSQL kaori_migrator password: ')
    if not migrator_password or migrator_password == runtime.password:
        _abort('migration password must be nonempty and distinct from runtime')
    migration_url = URL.create(
        'postgresql', username='kaori_migrator',
        password=migrator_password, host='db', port=5432, database='kaori',
    ).render_as_string(hide_password=False)

    # Validate the actual login before invoking Flask-Migrate.
    try:
        with psycopg2.connect(
            host='db', port=5432, dbname='kaori',
            user='kaori_migrator', password=migrator_password,
            connect_timeout=5, application_name='kaori-dev-migrator-preflight',
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT current_user, current_database(),
                              (SELECT rolsuper OR rolcreatedb OR rolcreaterole
                               OR rolreplication OR rolbypassrls
                               FROM pg_roles WHERE rolname = current_user),
                              has_schema_privilege(current_user, 'public', 'CREATE')"""
                )
                if cursor.fetchone() != ('kaori_migrator', 'kaori', False, True):
                    _abort('the configured DDL identity/privileges are invalid')
    except psycopg2.Error:
        _abort('migration login or schema authorization failed (credentials not logged)')

    print('KAORI database: applying explicit non-superuser Alembic/RBAC migration...')
    migrate_env = {**os.environ, 'KAORI_DB_MIGRATION_URL': migration_url}
    subprocess.run(['sh', 'scripts/init_db.sh'], env=migrate_env, check=True)

    # Scope credential to the psql grants child process; the worker/Beat
    # environment and canonical application DATABASE_URL never change.
    grant_env = {
        **os.environ, 'PGPASSWORD': migrator_password,
        'PGAPPNAME': 'kaori-devcontainer-role-provision',
    }
    print('KAORI database: refreshing reviewed immutable runtime grants...')
    subprocess.run(
        [
            'psql', '-X', '-h', 'db', '-U', 'kaori_migrator', '-d', 'kaori',
            '-v', 'ON_ERROR_STOP=1', '-v', 'kaori_devcontainer_confirm=1',
            '-f', 'scripts/devcontainer/provision_postgres_runtime_role.sql',
        ],
        env=grant_env, check=True,
    )

    # Bootstrap the KAORI first administrator with normal application grants.
    # This command is not a PostgreSQL CREATE ROLE operation.
    if args.bootstrap_admin:
        print('KAORI database: initializing application administrator as restricted runtime...')
        subprocess.run(['flask', '--app', 'run:app', 'bootstrap-admin'], env=os.environ.copy(), check=True)

    from app.extensions.db import db
    from app.kubernetes.tenant.capsule_handoff_start_writer import (
        _require_postgres_ledger_write_once_guards,
    )
    from run import app

    with app.app_context():
        try:
            if db.engine.url.username != 'kaori_runtime':
                _abort('Flask ORM resolved an elevated or unexpected runtime identity')
            _require_postgres_ledger_write_once_guards(db.session)
        finally:
            db.session.rollback()

    print('PASS: migration, runtime ACLs and Capsule ledger guard admitted.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.CalledProcessError):
        print('Database initialization failed; inspect step output, no credentials logged.', file=sys.stderr)
        raise SystemExit(1) from None
