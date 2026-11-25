"""Dedicated DB preparation against the exact disposable PostgreSQL CI fixture (#5202)."""

from __future__ import annotations

import os
import subprocess
from contextlib import closing
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / 'deploy/server/secret-store/prepare-storage-database.sql'
CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'
ROLES = ('kaori_runtime', 'kaori_migrator', 'kaori_secret_store_owner', 'kaori_secret_store')
DATABASES = ('kaori', 'kaori_secret_store')


def _prepare(database: str, *, opt_in: bool = True) -> subprocess.CompletedProcess[str]:
    command = ['psql', '--no-psqlrc', '--file', str(PREPARE)]
    if opt_in:
        command.append('--set=kaori_secret_store_prepare=true')
    return subprocess.run(
        command,
        env={
            'PATH': os.environ['PATH'],
            'PGHOST': 'postgres',
            'PGPORT': '5432',
            'PGUSER': 'postgres',
            'PGPASSWORD': 'postgres',
            'PGDATABASE': database,
            'PGCONNECT_TIMEOUT': '5',
        },
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def test_prepare_storage_database_disposable_postgresql() -> None:
    if (
        os.environ.get('APP_ENV') != 'testing'
        or os.environ.get('TEST_DATABASE_URL') != CI_DSN
        or os.environ.get('DATABASE_URL') != CI_DSN
    ):
        pytest.skip('Requires the exact isolated KAORI CI PostgreSQL fixture.')

    with closing(psycopg2.connect(CI_DSN, connect_timeout=5)) as admin:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute('SELECT datname FROM pg_database WHERE datname = ANY(%s)', (list(DATABASES),))
            assert cursor.fetchall() == [], 'Refusing pre-existing fixture database names.'
            cursor.execute('SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)', (list(ROLES),))
            assert cursor.fetchall() == [], 'Refusing pre-existing fixture role names.'
            created_roles: list[str] = []
            app_created = False
            attempted = False
            try:
                for role in ROLES[:2]:
                    cursor.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
                    created_roles.append(role)
                cursor.execute('CREATE DATABASE kaori OWNER kaori_migrator')
                app_created = True
                result = _prepare('postgres', opt_in=False)
                assert result.returncode != 0 and 'opt-in required' in result.stderr
                result = _prepare('kaori_test')
                assert result.returncode != 0 and 'primary maintenance database' in result.stderr
                result = _prepare('postgres')
                assert result.returncode != 0 and 'PUBLIC CONNECT' in result.stderr
                cursor.execute('SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)', (list(ROLES[2:]),))
                assert cursor.fetchall() == []
                cursor.execute('REVOKE ALL ON DATABASE kaori FROM PUBLIC')
                cursor.execute('GRANT CONNECT ON DATABASE kaori TO kaori_runtime')
                attempted = True
                result = _prepare('postgres')
                assert result.returncode == 0, result.stderr
                result = _prepare('postgres')
                assert result.returncode != 0 and 'Existing Secret Store database or role' in result.stderr
                cursor.execute(
                    'SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls '
                    'FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname',
                    (list(ROLES[2:]),),
                )
                assert cursor.fetchall() == [
                    ('kaori_secret_store', False, False, False, False, False, False),
                    ('kaori_secret_store_owner', False, False, False, False, False, False),
                ]
                cursor.execute(
                    "SELECT datallowconn, pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'kaori_secret_store'"
                )
                assert cursor.fetchone() == (True, 'kaori_secret_store_owner')
                cursor.execute(
                    "SELECT has_database_privilege('kaori_secret_store', 'kaori_secret_store', 'CONNECT'), "
                    "has_database_privilege('kaori_secret_store', 'kaori', 'CONNECT'), "
                    "has_database_privilege('kaori_runtime', 'kaori_secret_store', 'CONNECT'), "
                    "has_database_privilege('kaori_migrator', 'kaori_secret_store', 'CONNECT')"
                )
                assert cursor.fetchone() == (True, False, False, False)
            finally:
                # Cleanup is restricted to the initially empty disposable CI fixture only.
                if attempted:
                    cursor.execute('DROP DATABASE IF EXISTS kaori_secret_store')
                    cursor.execute('DROP ROLE IF EXISTS kaori_secret_store')
                    cursor.execute('DROP ROLE IF EXISTS kaori_secret_store_owner')
                if app_created:
                    cursor.execute('DROP DATABASE kaori')
                for role in reversed(created_roles):
                    cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
