"""Pure host-side first-run contract tests; never connect to Docker or mutate KAORI DB."""
from __future__ import annotations

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / '.devcontainer' / 'prepare-postgres-env.py'


def _initialization(tmp_path: Path, *, volume_exists: dict[str, bool]):
    # Load the real initializer under an inert run_name, then redirect ALL
    # host filesystem authority into pytest's ephemeral tmp_path.
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_test')
    main = namespace['main']
    state = main.__globals__
    state['ROOT'] = tmp_path
    state['APP_ENV'] = tmp_path / '.env'
    state['SECRET_DIR'] = tmp_path / 'private-home' / '.config' / 'kaori' / 'devcontainer'
    state['DB_SECRETS'] = state['SECRET_DIR'] / 'postgres-bootstrap.env'
    state['MIGRATOR_SECRETS'] = state['SECRET_DIR'] / 'postgres-migrate.env'
    state['database_volume_exists'] = lambda: volume_exists['value']
    (tmp_path / '.env.example').write_text(
        'POSTGRES_DB=kaori\n'
        'POSTGRES_USER=postgres\n'
        'POSTGRES_PASSWORD=old-owner-dev-password\n'
        'DATABASE_URL=postgresql://postgres:old-owner-dev-password@db:5432/kaori\n'
        'SECRET_KEY=replace-dev\n'
        'INTEGRATION_CREDENTIAL_KEY=\n'
        'ADMIN_PASSWORD=replace-dev\n',
        encoding='utf-8',
    )
    return main, state


def test_empty_volume_creates_segregated_roles_secrets_and_runtime_url(tmp_path: Path) -> None:
    volume = {'value': False}
    main, state = _initialization(tmp_path, volume_exists=volume)
    main()
    app_source = state['APP_ENV'].read_text()
    admin_source = state['DB_SECRETS'].read_text()
    migrator_source = state['MIGRATOR_SECRETS'].read_text()
    assert 'DATABASE_URL=postgresql://kaori_runtime:' in app_source
    assert 'POSTGRES_USER=postgres' in app_source
    assert not any(line.startswith('POSTGRES_PASSWORD=') for line in app_source.splitlines())
    assert 'KAORI_MIGRATOR_PASSWORD' not in app_source
    assert 'KAORI_RUNTIME_PASSWORD' not in app_source
    assert 'POSTGRES_PASSWORD=' in admin_source
    assert 'KAORI_RUNTIME_PASSWORD=' in admin_source
    assert 'KAORI_MIGRATOR_PASSWORD=' in migrator_source
    assert 'POSTGRES_PASSWORD' not in migrator_source
    assert state['DB_SECRETS'].stat().st_mode & 0o777 == 0o600
    assert state['MIGRATOR_SECRETS'].stat().st_mode & 0o777 == 0o600
    assert state['SECRET_DIR'].stat().st_mode & 0o777 == 0o700
    assert state['APP_ENV'].stat().st_mode & 0o777 == 0o600

    # A second Reopen does NOT rotate identities, encryption key or admin.
    volume['value'] = True
    main()
    assert state['APP_ENV'].read_text() == app_source
    assert state['DB_SECRETS'].read_text() == admin_source
    assert state['MIGRATOR_SECRETS'].read_text() == migrator_source


def test_existing_database_rejects_missing_application_env(tmp_path: Path) -> None:
    main, state = _initialization(tmp_path, volume_exists={'value': True})
    with pytest.raises(SystemExit, match='application .env is missing'):
        main()
    assert not state['APP_ENV'].exists()
    assert not state['DB_SECRETS'].exists()


def test_existing_database_rejects_missing_bootstrap_secrets(tmp_path: Path) -> None:
    volume = {'value': False}
    main, state = _initialization(tmp_path, volume_exists=volume)
    main()
    volume['value'] = True
    state['DB_SECRETS'].unlink()
    with pytest.raises(SystemExit, match='only one bootstrap secret file exists'):
        main()


def test_existing_database_rejects_runtime_credential_drift(tmp_path: Path) -> None:
    volume = {'value': False}
    main, state = _initialization(tmp_path, volume_exists=volume)
    main()
    volume['value'] = True
    app_env = state['APP_ENV']
    tampered = app_env.read_text().replace(
        'DATABASE_URL=postgresql://kaori_runtime:',
        'DATABASE_URL=postgresql://postgres:',
    )
    app_env.write_text(tampered)
    with pytest.raises(SystemExit, match='runtime DATABASE_URL differs'):
        main()
    assert app_env.read_text() == tampered


def test_docker_inspect_missing_volume_is_the_only_allowed_fresh_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_inspect')
    inspect_volume = namespace['database_volume_exists']
    module = namespace['subprocess']
    monkeypatch.setattr(
        module, 'run',
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr='Error response from daemon: get kaori-dev_kaori_postgres_data: no such volume',
            stdout='',
        ),
    )
    assert inspect_volume() is False


def test_docker_inspect_daemon_failure_never_regenerates_database_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_inspect')
    monkeypatch.setattr(
        namespace['subprocess'], 'run',
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stderr='Cannot connect to the Docker daemon', stdout='',
        ),
    )
    with pytest.raises(SystemExit, match='Docker volume inspection failed'):
        namespace['database_volume_exists']()


def test_docker_inspect_rejects_same_name_volume_owned_by_other_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_inspect')
    inspect = [{
        'Name': 'kaori-dev_kaori_postgres_data',
        'Labels': {
            'com.docker.compose.project': 'foreign-project',
            'com.docker.compose.volume': 'kaori_postgres_data',
        },
    }]
    monkeypatch.setattr(
        namespace['subprocess'], 'run',
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stderr='', stdout=json.dumps(inspect),
        ),
    )
    with pytest.raises(SystemExit, match='identity/ownership differs'):
        namespace['database_volume_exists']()


def test_docker_inspect_accepts_only_correct_kaori_dev_volume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(PREPARE), run_name='kaori_first_run_inspect')
    inspect = [{
        'Name': 'kaori-dev_kaori_postgres_data',
        'Labels': {
            'com.docker.compose.project': 'kaori-dev',
            'com.docker.compose.volume': 'kaori_postgres_data',
        },
    }]
    monkeypatch.setattr(
        namespace['subprocess'], 'run',
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stderr='', stdout=json.dumps(inspect),
        ),
    )
    assert namespace['database_volume_exists']() is True
