"""Regression contracts for data-preserving legacy Docker secret-volume recovery."""

from __future__ import annotations

import runpy
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[3]
RECOVERY = ROOT / '.devcontainer' / 'recover-legacy-postgres-secrets.py'


def _environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    scope = runpy.run_path(str(RECOVERY), run_name='kaori_legacy_secret_recovery_test')
    global_vars = scope['main'].__globals__
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    legacy_admin = tmp_path / 'legacy-admin'
    legacy_migrator = tmp_path / 'legacy-migrator'
    pgdata = tmp_path / 'pgdata'
    for folder in (legacy_admin, legacy_migrator, pgdata):
        folder.mkdir()
    (checkout / '.env.example').write_text('APP_ENV=development\n')
    (pgdata / 'PG_VERSION').write_text('16\n')
    admin_pwd = 'a' * 30
    runtime_pwd = 'b' * 30
    migrator_pwd = 'c' * 30
    (legacy_admin / 'postgres_password').write_text(admin_pwd)
    (legacy_admin / 'runtime_password').write_text(runtime_pwd)
    (legacy_migrator / 'password').write_text(migrator_pwd)
    app_env = checkout / '.env'
    original = (
        'APP_ENV=development\n'
        'DATABASE_URL=postgresql://kaori_runtime:' + quote(runtime_pwd, safe='') + '@db:5432/kaori\n'
        'ADMIN_EMAIL=keep@example.invalid\n'
    )
    app_env.write_text(original)
    secrets_dir = checkout / 'secrets' / 'devcontainer'
    global_vars.update(
        {
            'ROOT': checkout,
            'APP_ENV': app_env,
            'PG_DATA': pgdata,
            'LEGACY_ADMIN': legacy_admin,
            'LEGACY_MIGRATOR': legacy_migrator,
            'SECRET_DIR': secrets_dir,
            'ADMIN_DEST': secrets_dir / 'postgres-bootstrap.env',
            'MIGRATOR_DEST': secrets_dir / 'postgres-migrate.env',
        }
    )
    monkeypatch.setenv('KAORI_DEV_LEGACY_RECOVERY', '1')
    return scope['main'], global_vars, original


def test_valid_legacy_secret_volumes_recover_local_files_without_changing_db_or_app_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, original = _environment(tmp_path, monkeypatch)
    assert recovery() == 0
    assert state['APP_ENV'].read_text() == original
    assert (state['PG_DATA'] / 'PG_VERSION').read_text() == '16\n'
    bootstrap = state['ADMIN_DEST'].read_text()
    migrator = state['MIGRATOR_DEST'].read_text()
    assert bootstrap == 'POSTGRES_PASSWORD=' + 'a' * 30 + '\nKAORI_RUNTIME_PASSWORD=' + 'b' * 30 + '\n'
    assert migrator == 'KAORI_MIGRATOR_PASSWORD=' + 'c' * 30 + '\n'
    assert recovery() == 0
    assert state['ADMIN_DEST'].read_text() == bootstrap
    assert state['MIGRATOR_DEST'].read_text() == migrator


def test_missing_app_env_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    state['APP_ENV'].unlink()
    with pytest.raises(SystemExit, match='app .env is missing'):
        recovery()
    assert not state['ADMIN_DEST'].exists()


def test_existing_app_credential_mismatch_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, original = _environment(tmp_path, monkeypatch)
    state['APP_ENV'].write_text(original.replace('kaori_runtime:', 'postgres:'))
    with pytest.raises(SystemExit, match='runtime DATABASE_URL differs'):
        recovery()
    assert not state['ADMIN_DEST'].exists()


def test_uninitialized_pgdata_does_not_admit_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    (state['PG_DATA'] / 'PG_VERSION').unlink()
    with pytest.raises(SystemExit, match='initialized PostgreSQL data volume'):
        recovery()


def test_missing_legacy_migrator_password_blocks_partial_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    (state['LEGACY_MIGRATOR'] / 'password').unlink()
    with pytest.raises(SystemExit, match='legacy Docker credential file is missing'):
        recovery()
    assert not state['ADMIN_DEST'].exists()


def test_mismatched_existing_repo_secret_aborts_both_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    state['SECRET_DIR'].mkdir(parents=True)
    state['MIGRATOR_DEST'].write_text('KAORI_MIGRATOR_PASSWORD=unexpected\n')
    with pytest.raises(SystemExit, match='existing ignored PostgreSQL ENV differs'):
        recovery()
    assert not state['ADMIN_DEST'].exists()


def test_partial_prior_copy_can_resume_only_with_exact_matching_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    state['SECRET_DIR'].mkdir(parents=True)
    state['ADMIN_DEST'].write_text('POSTGRES_PASSWORD=' + 'a' * 30 + '\nKAORI_RUNTIME_PASSWORD=' + 'b' * 30 + '\n')
    assert recovery() == 0
    assert state['MIGRATOR_DEST'].is_file()


def test_recovery_requires_manual_operator_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, _, _ = _environment(tmp_path, monkeypatch)
    monkeypatch.delenv('KAORI_DEV_LEGACY_RECOVERY')
    with pytest.raises(SystemExit, match='explicit operator'):
        recovery()


def test_recovery_rejects_external_symlink_credential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, state, _ = _environment(tmp_path, monkeypatch)
    secret = state['LEGACY_MIGRATOR'] / 'password'
    secret.unlink()
    secret.symlink_to(state['LEGACY_ADMIN'] / 'runtime_password')
    with pytest.raises(SystemExit, match='missing or symlinked'):
        recovery()


def test_manual_command_is_documented_with_read_only_mounts() -> None:
    runbook = (ROOT / 'docs/operations/devcontainer-postgres-first-run.md').read_text()
    assert 'KAORI_DEV_LEGACY_RECOVERY=1' in runbook
    assert 'kaori-dev-pg-admin-secrets' in runbook
    assert 'kaori-dev-pg-migrator-secrets' in runbook
    assert 'target=/pgdata,readonly' in runbook
    assert 'target=/legacy-admin,readonly' in runbook
    assert 'target=/legacy-migrator,readonly' in runbook
