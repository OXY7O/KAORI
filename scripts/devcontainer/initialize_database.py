"""One explicit DevContainer task for owner-only schema/RBAC/admin bootstrap.

The first-run UI stays read-only. This operator-invoked command is NOT
executed at every VS Code container start; it reuses the canonical
scripts/init_db.sh and existing immutable-ledger GRANT SQL.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from sqlalchemy.engine import URL, make_url


def _abort(message: str) -> None:
    raise RuntimeError(f'DevContainer database initialization refused: {message}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Initialize or upgrade local KAORI database as its owner')
    parser.add_argument(
        '--bootstrap-admin', action='store_true',
        help='Create the initial KAORI administrator after owner migrations and RBAC seed',
    )
    args = parser.parse_args()

    if os.getenv('APP_ENV') != 'development':
        _abort('not running in the development runtime')
    if os.getenv('KAORI_DB_MIGRATION_URL'):
        _abort('remove ambient migration URL; this task creates a temporary owner connection')
    if (
        os.getenv('POSTGRES_USER') != 'kaori'
        or os.getenv('POSTGRES_DB') != 'kaori'
        or not os.getenv('POSTGRES_PASSWORD')
    ):
        _abort('local PostgreSQL bootstrap owner configuration is missing or unexpected')

    runtime_raw = os.getenv('DATABASE_URL', '')
    if not runtime_raw:
        _abort('canonical runtime DATABASE_URL is missing')
    runtime = make_url(runtime_raw)
    if (
        runtime.username != 'kaori_runtime' or runtime.host != 'db'
        or runtime.database != 'kaori' or (runtime.port or 5432) != 5432
        or not runtime.password
    ):
        _abort('runtime DATABASE_URL does not describe the expected restricted local role')
    if runtime.password == os.environ['POSTGRES_PASSWORD']:
        _abort('runtime and owner passwords must differ')

    # Owner authority is never saved in .env or inherited by workers.
    migration_url = URL.create(
        'postgresql',
        username=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host='db',
        port=5432,
        database='kaori',
    ).render_as_string(hide_password=False)
    migrate_env = {**os.environ, 'KAORI_DB_MIGRATION_URL': migration_url}
    print('KAORI database setup: owner migrations + application RBAC...')
    subprocess.run(
        ['sh', 'scripts/init_db.sh', *(['--bootstrap-admin'] if args.bootstrap_admin else [])],
        env=migrate_env,
        check=True,
    )

    # Reuse the existing transactional, checked grants script; future
    # migrations must refresh privileges because default grants are withheld.
    role_env = {
        **os.environ,
        'PGPASSWORD': os.environ['POSTGRES_PASSWORD'],
        'PGAPPNAME': 'kaori-devcontainer-role-provision',
    }
    print('KAORI database setup: applying restricted runtime table grants...')
    subprocess.run(
        [
            'psql', '-X', '-h', 'db', '-U', 'kaori', '-d', 'kaori',
            '-v', 'ON_ERROR_STOP=1', '-v', 'kaori_devcontainer_confirm=1',
            '-f', 'scripts/devcontainer/provision_postgres_runtime_role.sql',
        ],
        env=role_env,
        check=True,
    )

    # Reuse the actual application-side fail-closed guard.
    from app.extensions.db import db
    from app.kubernetes.tenant.capsule_handoff_start_writer import (
        _require_postgres_ledger_write_once_guards,
    )
    from run import app

    with app.app_context():
        try:
            if db.engine.url.username != 'kaori_runtime':
                _abort('Flask ORM resolved an elevated or unexpected runtime role')
            _require_postgres_ledger_write_once_guards(db.session)
        finally:
            db.session.rollback()

    print('PASS: KAORI migrated; restricted runtime grants and Capsule ledger guard admitted.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        # Avoid echoing shell or connection strings, including role password.
        print(f'Database initialization failed ({type(exc).__name__}); see preceding '
              'step output and keep provider actions disabled.', file=sys.stderr)
        raise SystemExit(1) from None
