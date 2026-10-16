"""Pure regression tests for #1427 repo-local ignored DevContainer DB env.

No PostgreSQL/database or Docker daemon is contacted.
"""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / '.devcontainer' / 'prepare-postgres-env.py'


def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_contract')
    scope = namespace['main'].__globals__
    workspace = tmp_path / 'checkout'
    workspace.mkdir()
    pgdata = tmp_path / 'pgdata'
    pgdata.mkdir()
    secret_dir = workspace / 'secrets' / 'devcontainer'
    scope.update(
        {
            'ROOT': workspace,
            'APP_ENV': workspace / '.env',
            'PG_DATA': pgdata,
            'SECRET_DIR': secret_dir,
            'ADMIN_ENV': secret_dir / 'postgres-bootstrap.env',
            'MIGRATOR_ENV': secret_dir / 'postgres-migrate.env',
            'BACKUP_ENV': secret_dir / 'application-env-before-three-role.bak',
        }
    )
    (workspace / '.env.example').write_text(
        'APP_ENV=development\n'
        'POSTGRES_DB=kaori\n'
        'POSTGRES_USER=postgres\n'
        'DATABASE_URL=postgresql://kaori_runtime:generated-by-devcontainer-initialize-command@db:5432/kaori\n'
        'SECRET_KEY=replace-placeholder\n'
        'INTEGRATION_CREDENTIAL_KEY=\n'
        'ADMIN_PASSWORD=replace-placeholder\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('KAORI_DEV_DOCKER_INIT', '1')
    return namespace['main'], scope


def test_local_env_update_preserves_order_deduplicates_and_is_idempotent() -> None:
    settings = runpy.run_path(str(PREPARE), run_name='kaori_env_order_contract')
    set_value = settings['set_value']
    current = '# operator context\nPOSTGRES_DB=old\nAPP_ENV=development\nPOSTGRES_DB=duplicate\n'
    expected = '# operator context\nPOSTGRES_DB=kaori\nAPP_ENV=development\n'
    assert set_value(current, 'POSTGRES_DB', 'kaori') == expected
    assert set_value(expected, 'POSTGRES_DB', 'kaori') == expected
    assert set_value(expected, 'POSTGRES_USER', 'postgres') == expected + 'POSTGRES_USER=postgres\n'


def test_fresh_volume_generates_repo_ignored_credentials_and_runtime_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    main()
    runtime = s['APP_ENV'].read_text()
    bootstrap = s['ADMIN_ENV'].read_text()
    migrator = s['MIGRATOR_ENV'].read_text()
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in runtime
    assert 'generated-by-devcontainer-initialize-command' not in runtime
    assert 'POSTGRES_PASSWORD=' not in runtime
    assert 'POSTGRES_PASSWORD=' in bootstrap
    assert 'KAORI_RUNTIME_PASSWORD=' in bootstrap
    assert 'KAORI_MIGRATOR_PASSWORD=' in migrator
    main()
    assert s['APP_ENV'].read_text() == runtime
    assert s['ADMIN_ENV'].read_text() == bootstrap
    assert s['MIGRATOR_ENV'].read_text() == migrator


def test_old_local_db_url_with_empty_pg_volume_is_backed_up_before_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    old = (
        'APP_ENV=development\n'
        'DATABASE_URL=postgresql://kaori:old-owner-secret@db:5432/kaori\n'
        'ADMIN_EMAIL=custom@example.invalid\n'
        'SECRET_KEY=preserve-me\n'
    )
    s['APP_ENV'].write_text(old)
    main()
    assert s['BACKUP_ENV'].read_text() == old
    updated = s['APP_ENV'].read_text()
    assert 'ADMIN_EMAIL=custom@example.invalid' in updated
    assert 'SECRET_KEY=preserve-me' in updated
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in updated
    assert 'old-owner-secret' not in updated


def test_preexisting_postgresql_data_never_gets_new_login_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    (s['PG_DATA'] / 'PG_VERSION').write_text('16\n')
    with pytest.raises(SystemExit, match='existing PostgreSQL data'):
        main()
    assert not s['ADMIN_ENV'].exists()
    assert not s['MIGRATOR_ENV'].exists()


def test_partial_cluster_directory_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    (s['PG_DATA'] / 'global').mkdir()
    with pytest.raises(SystemExit, match='nonempty but uninitialized'):
        main()


def test_partial_secrets_and_missing_app_env_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    main()
    s['MIGRATOR_ENV'].unlink()
    with pytest.raises(SystemExit, match='incomplete repo-local'):
        main()
    s['MIGRATOR_ENV'].write_text('KAORI_MIGRATOR_PASSWORD=recovered-original-secret\n')
    s['APP_ENV'].unlink()
    with pytest.raises(SystemExit, match='application .env is absent'):
        main()


def test_existing_mismatched_runtime_url_aborts_without_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    main()
    modified = s['APP_ENV'].read_text().replace('kaori_runtime:', 'postgres:')
    s['APP_ENV'].write_text(modified)
    with pytest.raises(SystemExit, match='mismatches existing secrets'):
        main()
    assert s['APP_ENV'].read_text() == modified


@pytest.mark.parametrize(
    'name',
    [
        'KAORI_MIGRATOR_PASSWORD',
        'KAORI_RUNTIME_PASSWORD',
        'KAORI_DB_MIGRATION_URL',
        'PGPASSWORD',
        'POSTGRES_PASSWORD_FILE',
    ],
)
def test_privileged_credentials_refused_in_shared_app_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    s['APP_ENV'].write_text(f'APP_ENV=development\n{name}=secret\n')
    with pytest.raises(SystemExit, match='must not be present in shared application'):
        main()
    assert not s['ADMIN_ENV'].exists()


def test_untrusted_external_database_url_cannot_be_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, s = _sandbox(tmp_path, monkeypatch)
    s['APP_ENV'].write_text('APP_ENV=development\nDATABASE_URL=postgresql://owner:secret@external.example:5432/prod\n')
    with pytest.raises(SystemExit, match='outside the approved local'):
        main()
    assert not s['ADMIN_ENV'].exists()


def test_native_windows_docker_command_checks_actual_db_volume() -> None:
    spec = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    cmd = spec['initializeCommand']
    assert cmd[:3] == ['docker', 'run', '--rm']
    assert 'python:3.12-alpine' in cmd
    assert 'KAORI_DEV_DOCKER_INIT=1' in cmd
    assert any('kaori-dev_kaori_postgres_data' in value for value in cmd)
    assert 'db-bootstrap' not in spec['runServices']
    compose = (ROOT / '.devcontainer/compose.devcontainer.yml').read_text()
    assert 'postgres-bootstrap.env' in compose
    assert 'postgres-migrate.env' in compose
    assert 'external: true' in compose
    assert 'kaori-dev_kaori_postgres_data' in compose
    assert 'kaori_dev_pg_admin_credentials' not in compose
    assert 'kaori_dev_pg_migrator_credentials' not in compose


def test_live_secret_directory_ignored_by_git_and_docker_build() -> None:
    assert '/secrets/' in (ROOT / '.gitignore').read_text()
    assert '/secrets/' in (ROOT / '.dockerignore').read_text()
    assert (ROOT / '.devcontainer/examples/postgres-bootstrap.env.example').is_file()
    assert (ROOT / '.devcontainer/examples/postgres-migrate.env.example').is_file()
