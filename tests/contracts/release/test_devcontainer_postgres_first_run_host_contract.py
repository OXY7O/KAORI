"""Docker-based first-run initializer checks; no Docker or database calls."""
from __future__ import annotations

import json
import os
import runpy
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / '.devcontainer' / 'prepare-postgres-env.py'


def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_docker_initializer_test')
    scope = namespace['main'].__globals__
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    admin = tmp_path / 'admin_volume'
    migrator = tmp_path / 'migrator_volume'
    admin.mkdir()
    migrator.mkdir()
    scope.update({
        'ROOT': checkout,
        'APP_ENV': checkout / '.env',
        'ADMIN_DIR': admin,
        'MIGRATOR_DIR': migrator,
        'ADMIN_SECRET': admin / 'postgres_password',
        'RUNTIME_SECRET': admin / 'runtime_password',
        'MIGRATOR_SECRET': migrator / 'password',
        'POSTGRES_UID': os.getuid(),
        'POSTGRES_GID': os.getgid(),
    })
    scope['ROLE_SECRETS'] = (
        scope['ADMIN_SECRET'], scope['RUNTIME_SECRET'], scope['MIGRATOR_SECRET'],
    )
    (checkout / '.env.example').write_text(
        'APP_ENV=development\n'
        'POSTGRES_DB=kaori\n'
        'POSTGRES_USER=postgres\n'
        'DATABASE_URL=postgresql://kaori_runtime:generated-by-devcontainer-initialize-command@db:5432/kaori\n'
        'SECRET_KEY=replace-with-placeholder\n'
        'INTEGRATION_CREDENTIAL_KEY=\n'
        'ADMIN_PASSWORD=replace-with-placeholder\n',
    )
    monkeypatch.setenv('KAORI_DEV_DOCKER_INIT', '1')
    return namespace['main'], scope


def test_three_passwords_and_reopen_stability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, scope = _sandbox(tmp_path, monkeypatch)
    main()
    env = scope['APP_ENV'].read_text()
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in env
    assert 'POSTGRES_PASSWORD=' not in env
    assert 'generated-by-devcontainer-initialize-command' not in env
    passwords = {scope[p].read_text() for p in (
        'ADMIN_SECRET', 'RUNTIME_SECRET', 'MIGRATOR_SECRET',
    )}
    assert len(passwords) == 3
    for p in ('ADMIN_SECRET', 'RUNTIME_SECRET', 'MIGRATOR_SECRET'):
        assert stat.S_IMODE(scope[p].stat().st_mode) == 0o600
    main()
    assert scope['APP_ENV'].read_text() == env


def test_missing_app_env_or_migrator_secret_refuses_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, scope = _sandbox(tmp_path, monkeypatch)
    main()
    env = scope['APP_ENV'].read_text()
    scope['APP_ENV'].unlink()
    with pytest.raises(SystemExit, match='missing app .env'):
        main()
    scope['APP_ENV'].write_text(env)
    scope['MIGRATOR_SECRET'].unlink()
    with pytest.raises(SystemExit, match='incomplete persistent PostgreSQL secrets'):
        main()


def test_runtime_credential_drift_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, scope = _sandbox(tmp_path, monkeypatch)
    main()
    tampered = scope['APP_ENV'].read_text().replace('kaori_runtime:', 'postgres:')
    scope['APP_ENV'].write_text(tampered)
    with pytest.raises(SystemExit, match='runtime URL does not match'):
        main()
    assert scope['APP_ENV'].read_text() == tampered


@pytest.mark.parametrize('key', [
    'KAORI_MIGRATOR_PASSWORD', 'KAORI_RUNTIME_PASSWORD',
    'KAORI_DB_MIGRATION_URL', 'PGPASSWORD', 'POSTGRES_PASSWORD_FILE',
])
def test_app_env_rejects_database_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str,
) -> None:
    main, scope = _sandbox(tmp_path, monkeypatch)
    scope['APP_ENV'].write_text(f'APP_ENV=development\n{key}=elevated\n')
    with pytest.raises(SystemExit, match='must not be present'):
        main()
    assert not scope['ADMIN_SECRET'].exists()


def test_non_development_app_env_or_untrusted_entrypoint_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    main, scope = _sandbox(tmp_path, monkeypatch)
    scope['APP_ENV'].write_text('APP_ENV=production\n')
    with pytest.raises(SystemExit, match='development-only'):
        main()
    monkeypatch.delenv('KAORI_DEV_DOCKER_INIT')
    with pytest.raises(SystemExit, match='isolated Docker initializeCommand'):
        main()


def test_native_windows_docker_works_without_python_or_wsl_host() -> None:
    spec = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
    command = spec['initializeCommand']
    assert command[:3] == ['docker', 'run', '--rm']
    assert 'python:3.12-alpine' in command
    assert 'KAORI_DEV_DOCKER_INIT=1' in command
    assert 'type=bind,source=' + chr(36) + '{localWorkspaceFolder},target=/workspace' in command
    assert 'db-bootstrap' not in spec['runServices']
    compose = (ROOT / '.devcontainer/compose.devcontainer.yml').read_text()
    assert chr(36) + '{HOME:' not in compose
    assert 'POSTGRES_PASSWORD_FILE: /run/kaori-admin/postgres_password' in compose
    assert 'kaori_dev_pg_admin_credentials:/run/kaori-admin:ro' in compose
    assert 'kaori_dev_pg_migrator_credentials:/run/kaori-migrator:ro' in compose
    bootstrap = compose.split('\n  db-bootstrap:\n', 1)[1].split('\nvolumes:', 1)[0]
    assert 'kaori_dev_pg_admin_credentials:' not in bootstrap
    assert 'kaori_dev_pg_migrator_credentials:/run/kaori-migrator:ro' in bootstrap
