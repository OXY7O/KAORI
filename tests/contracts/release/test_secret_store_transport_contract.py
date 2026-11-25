"""Storage transport negative regression on the existing isolated CI fixture (#5202)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERIFY = ROOT / 'deploy/server/secret-store/verify-storage-transport.sql'
CI_DSN = 'postgresql://postgres:postgres@postgres:5432/kaori_test'


def test_secret_store_transport_read_only_contract() -> None:
    source = VERIFY.read_text(encoding='utf-8')
    assert 'BEGIN READ ONLY;' in source
    assert 'pg_stat_ssl' in source
    assert "version IN ('TLSv1.2', 'TLSv1.3')" in source
    assert 'session_user <> current_user' in source
    assert 'FROM public.openbao_kv_store' not in source


def test_secret_store_transport_rejects_cleartext_ci_session() -> None:
    if (
        os.environ.get('APP_ENV') != 'testing'
        or os.environ.get('TEST_DATABASE_URL') != CI_DSN
        or os.environ.get('DATABASE_URL') != CI_DSN
    ):
        pytest.skip('Requires the exact isolated KAORI CI PostgreSQL fixture.')

    result = subprocess.run(
        ['psql', '--no-psqlrc', '--file', str(VERIFY)],
        env={
            'PATH': os.environ['PATH'],
            'PGHOST': 'postgres',
            'PGPORT': '5432',
            'PGUSER': 'postgres',
            'PGPASSWORD': 'postgres',
            'PGDATABASE': 'kaori_test',
            'PGSSLMODE': 'disable',
            'PGCONNECT_TIMEOUT': '5',
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert 'requires an encrypted TLS 1.2+ session' in result.stderr
