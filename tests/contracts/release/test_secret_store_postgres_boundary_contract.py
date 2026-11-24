"""Execute the dedicated Secret Store schema against the isolated CI PostgreSQL (#5202)."""

from __future__ import annotations

import os
import subprocess
from contextlib import closing
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / 'deploy/server/secret-store/provision-storage-schema.sql'
CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'
DATABASES = ('kaori', 'kaori_secret_store')
ROLES = ('kaori_runtime', 'kaori_migrator', 'kaori_secret_store_owner', 'kaori_secret_store')


def _run_schema(database: str) -> subprocess.CompletedProcess[str]:
    env = {
        'PATH': os.environ['PATH'],
        'PGHOST': 'postgres',
        'PGPORT': '5432',
        'PGUSER': 'postgres',
        'PGPASSWORD': 'postgres',
        'PGDATABASE': database,
        'PGCONNECT_TIMEOUT': '5',
    }
    return subprocess.run(
        ['psql', '--no-psqlrc', '--file', str(SCHEMA)],
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def _assert_refused(database: str, reason: str) -> None:
    result = _run_schema(database)
    assert result.returncode != 0
    assert reason in result.stderr


def test_secret_store_schema_declares_transaction_and_no_destructive_provisioning() -> None:
    source = SCHEMA.read_text(encoding='utf-8')
    assert '\\set ON_ERROR_STOP on' in source
    assert 'BEGIN;' in source and 'COMMIT;' in source
    assert 'DROP DATABASE' not in source
    assert 'DROP ROLE' not in source
    assert 'DROP TABLE' not in source
    assert 'TRUNCATE TABLE' not in source
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.openbao_kv_store' in source


def test_secret_store_schema_real_postgresql_boundary() -> None:
    # Never create or clean up these fixed operational names outside the canonical
    # disposable CI service. Refuse pre-existing names even there.
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
            assert cursor.fetchall() == [], 'Refusing existing fixture database names.'
            cursor.execute('SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)', (list(ROLES),))
            assert cursor.fetchall() == [], 'Refusing existing fixture role names.'
            created_roles: list[str] = []
            created_databases: list[str] = []
            try:
                for role in ROLES:
                    login = sql.SQL('NOLOGIN' if role.endswith('_owner') else 'LOGIN')
                    cursor.execute(
                        sql.SQL(
                            'CREATE ROLE {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'
                        ).format(sql.Identifier(role), login)
                    )
                    created_roles.append(role)
                cursor.execute('CREATE DATABASE kaori OWNER kaori_migrator')
                created_databases.append('kaori')
                cursor.execute('CREATE DATABASE kaori_secret_store OWNER kaori_secret_store_owner')
                created_databases.append('kaori_secret_store')
                _assert_refused('kaori_test', 'outside its primary dedicated database')
                _assert_refused('kaori_secret_store', 'can connect to application database')
                cursor.execute('REVOKE ALL ON DATABASE kaori FROM PUBLIC')
                cursor.execute('GRANT CONNECT ON DATABASE kaori TO kaori_runtime')
                with closing(psycopg2.connect(CI_DSN, dbname='kaori_secret_store', connect_timeout=5)):
                    _assert_refused('kaori_secret_store', 'Other sessions remain')
                result = _run_schema('kaori_secret_store')
                assert result.returncode == 0, result.stderr
                _assert_refused('kaori_secret_store', 'Existing schema objects detected')

                with closing(psycopg2.connect(CI_DSN, dbname='kaori_secret_store', connect_timeout=5)) as storage:
                    storage.autocommit = True
                    with storage.cursor() as db:
                        db.execute("SELECT to_regclass('public.openbao_kv_store_idx') IS NOT NULL")
                        assert db.fetchone() == (True,)
                        db.execute('SET ROLE kaori_secret_store')
                        db.execute(
                            'INSERT INTO public.openbao_kv_store (parent_path, path, key, value) VALUES (%s, %s, %s, %s)',
                            ('fixture/', 'fixture/', 'one', b'initial'),
                        )
                        db.execute('UPDATE public.openbao_kv_store SET value = %s WHERE key = %s', (b'changed', 'one'))
                        db.execute('SELECT value FROM public.openbao_kv_store WHERE key = %s', ('one',))
                        row = db.fetchone()
                        assert row is not None and bytes(row[0]) == b'changed'
                        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                            db.execute('CREATE TABLE public.denied (id int)')
                        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                            db.execute('TRUNCATE TABLE public.openbao_kv_store')
                        db.execute('DELETE FROM public.openbao_kv_store WHERE key = %s', ('one',))
                        assert db.rowcount == 1
                        db.execute('RESET ROLE')
                        db.execute('SET ROLE kaori_runtime')
                        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                            db.execute('SELECT value FROM public.openbao_kv_store')
            finally:
                for database in reversed(created_databases):
                    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
                for role in reversed(created_roles):
                    cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
