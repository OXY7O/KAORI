#!/usr/bin/env python3
"""Cross-platform local DevContainer PostgreSQL configuration preparation.

The Windows/Linux host launches this with a short-lived Docker Python
container, not a host Python/WSL prerequisite. PostgreSQL credentials are
stored in ignored repository-local /secrets/devcontainer/ env files. This
is trusted local development ONLY: repository bind mounts allow workspace
processes to read the files, so they are not production-grade isolation.

An explicitly mounted, read-only kaori-dev PostgreSQL data volume is the
first-install authority. NEVER rotate/replace credentials for populated data.
Alembic and the first application administrator remain operator-triggered.
"""
from __future__ import annotations

import base64
import os
import secrets
import stat
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path('/workspace')
APP_ENV = ROOT / '.env'
PG_DATA = Path('/pgdata')
SECRET_DIR = ROOT / 'secrets' / 'devcontainer'
ADMIN_ENV = SECRET_DIR / 'postgres-bootstrap.env'
MIGRATOR_ENV = SECRET_DIR / 'postgres-migrate.env'
BACKUP_ENV = SECRET_DIR / 'application-env-before-three-role.bak'
RUNTIME_ROLE = 'kaori_runtime'
PLACEHOLDER = (
    'postgresql://kaori_runtime:'
    'generated-by-devcontainer-initialize-command@db:5432/kaori'
)


def abort(message: str) -> None:
    raise SystemExit(f'KAORI DevContainer PostgreSQL: ABORT: {message}')


def env_values(source: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in source.splitlines():
        if line and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


def set_value(source: str, key: str, value: str) -> str:
    lines = [line for line in source.splitlines() if not line.startswith(f'{key}=')]
    lines.append(f'{key}={value}')
    return '\n'.join(lines) + '\n'


def drop_value(source: str, key: str) -> str:
    return '\n'.join(line for line in source.splitlines() if not line.startswith(f'{key}=')) + '\n'


def check_regular_file(path: Path) -> None:
    if path.is_symlink():
        abort('local database config must not be a symlink')
    if path.exists() and not path.is_file():
        abort('local database config must be a regular file')


def create_private(path: Path, value: str) -> None:
    check_regular_file(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                   'w', encoding='utf-8') as stream:
        stream.write(value)
    # On Windows bind mounts, host NTFS ACLs are the effective control.
    try:
        path.chmod(0o600)
    except OSError:
        pass


def check_pgdata() -> bool:
    if not PG_DATA.is_dir():
        abort('PostgreSQL Docker data volume is not mounted for safe first-run inspection')
    if (PG_DATA / 'PG_VERSION').is_file():
        return True
    if any(PG_DATA.iterdir()):
        abort('PostgreSQL volume is nonempty but uninitialized; preserve and review it')
    return False


def valid_local_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme.startswith('postgresql')
            and parsed.hostname == 'db'
            and (parsed.port or 5432) == 5432
            and parsed.path == '/kaori'
            and parsed.username in ('postgres', 'kaori', RUNTIME_ROLE)
            and bool(parsed.password)
        )
    except ValueError:
        return False


def main() -> None:
    if os.getenv('KAORI_DEV_DOCKER_INIT') != '1':
        abort('cross-platform Docker initializeCommand is required')
    if not (ROOT / '.env.example').is_file():
        abort('repository workspace is not mounted at /workspace')
    check_regular_file(APP_ENV)
    check_regular_file(ADMIN_ENV)
    check_regular_file(MIGRATOR_ENV)
    check_regular_file(BACKUP_ENV)

    data_exists = check_pgdata()
    source = (
        APP_ENV.read_text(encoding='utf-8') if APP_ENV.exists()
        else (ROOT / '.env.example').read_text(encoding='utf-8')
    )
    values = env_values(source)
    if values.get('APP_ENV', 'development') != 'development':
        abort('only development APP_ENV may use bundled PostgreSQL provisioning')
    if values.get('POSTGRES_DB', 'kaori') != 'kaori':
        abort('expected local PostgreSQL DB name kaori')
    if values.get('POSTGRES_USER', 'postgres') not in ('postgres', 'kaori'):
        abort('unexpected local PostgreSQL bootstrap username')
    for key in (
        'KAORI_MIGRATOR_PASSWORD', 'KAORI_RUNTIME_PASSWORD',
        'KAORI_DB_MIGRATION_URL', 'PGPASSWORD', 'POSTGRES_PASSWORD_FILE',
    ):
        if key in values:
            abort(f'{key} must not be present in shared application .env')

    if ADMIN_ENV.exists() != MIGRATOR_ENV.exists():
        abort('incomplete repo-local database credential files; recover them')
    credentials_exist = ADMIN_ENV.exists()
    if data_exists and not credentials_exist:
        abort('existing PostgreSQL data has no matching local secrets; recovery required')
    if credentials_exist and not APP_ENV.exists():
        abort('database credentials exist but application .env is absent; recover it')

    configured_url = values.get('DATABASE_URL', '')
    if configured_url and configured_url != PLACEHOLDER and not valid_local_url(configured_url):
        abort('DATABASE_URL points outside the approved local DevContainer database')

    if credentials_exist:
        a = env_values(ADMIN_ENV.read_text(encoding='utf-8'))
        m = env_values(MIGRATOR_ENV.read_text(encoding='utf-8'))
        if set(a) != {'POSTGRES_PASSWORD', 'KAORI_RUNTIME_PASSWORD'} or set(m) != {'KAORI_MIGRATOR_PASSWORD'}:
            abort('invalid local PostgreSQL credential-file authority')
        if len({a['POSTGRES_PASSWORD'], a['KAORI_RUNTIME_PASSWORD'], m['KAORI_MIGRATOR_PASSWORD']}) != 3:
            abort('PostgreSQL role credentials must be different')
        if not all(len(p) >= 16 for p in (*a.values(), *m.values())):
            abort('invalid persisted PostgreSQL role credential')
        runtime_pw = a['KAORI_RUNTIME_PASSWORD']
        expected_url = f'postgresql://kaori_runtime:{quote(runtime_pw, safe="")}@db:5432/kaori'
        if configured_url != expected_url:
            abort('runtime DATABASE_URL mismatches existing secrets; no silent rotation')
    else:
        # No first-volume secrets is safe only when PostgreSQL data volume is empty.
        # A previous (legacy) .env is preserved byte-for-byte BEFORE modifying
        # DATABASE_URL; all unrelated configuration stays as provided.
        if APP_ENV.exists() and configured_url and configured_url != PLACEHOLDER:
            SECRET_DIR.mkdir(parents=True, exist_ok=True)
            if BACKUP_ENV.exists():
                abort('existing migration backup is present; manual review required')
            create_private(BACKUP_ENV, source)
            print('KAORI: backed up existing app env before fresh-volume URL reconciliation')
        admin_pw = secrets.token_urlsafe(36)
        runtime_pw = secrets.token_urlsafe(36)
        migrate_pw = secrets.token_urlsafe(36)
        SECRET_DIR.mkdir(parents=True, exist_ok=True)
        create_private(ADMIN_ENV,
                       f'POSTGRES_PASSWORD={admin_pw}\nKAORI_RUNTIME_PASSWORD={runtime_pw}\n')
        create_private(MIGRATOR_ENV, f'KAORI_MIGRATOR_PASSWORD={migrate_pw}\n')
        expected_url = f'postgresql://kaori_runtime:{quote(runtime_pw, safe="")}@db:5432/kaori'

    source = drop_value(source, 'POSTGRES_PASSWORD')
    source = drop_value(source, 'KAORI_DEV_RUNTIME_DATABASE_URL')
    source = set_value(source, 'POSTGRES_DB', 'kaori')
    source = set_value(source, 'POSTGRES_USER', 'postgres')
    source = set_value(source, 'DATABASE_URL', expected_url)
    if not values.get('SECRET_KEY') or values['SECRET_KEY'].startswith('replace-'):
        if data_exists:
            abort('existing database with placeholder application SECRET_KEY')
        source = set_value(source, 'SECRET_KEY', secrets.token_urlsafe(48))
    if not values.get('INTEGRATION_CREDENTIAL_KEY'):
        if data_exists:
            abort('existing database with absent integration encryption key')
        source = set_value(
            source, 'INTEGRATION_CREDENTIAL_KEY',
            base64.urlsafe_b64encode(os.urandom(32)).decode('ascii'),
        )
    if not values.get('ADMIN_PASSWORD') or values['ADMIN_PASSWORD'].startswith('replace-'):
        if data_exists:
            abort('existing database with placeholder first-admin password')
        source = set_value(source, 'ADMIN_PASSWORD', secrets.token_urlsafe(32))
    if not APP_ENV.exists():
        create_private(APP_ENV, source)
    elif APP_ENV.read_text(encoding='utf-8') != source:
        APP_ENV.write_text(source, encoding='utf-8')
    print('KAORI DevContainer: private local database ENV ready; runtime remains kaori_runtime')
    print('KAORI DevContainer: schema migration and first admin require explicit db-bootstrap')


if __name__ == '__main__':
    main()
