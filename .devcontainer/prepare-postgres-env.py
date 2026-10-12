#!/usr/bin/env python3
"""Host-independent DevContainer env provisioning inside a short-lived Docker container.

Called via the Dev Containers initializeCommand Docker CLI on native Windows
or Linux. App .env stays inside the ignored checkout, while PostgreSQL role
secrets live in two *separate* named Docker volumes not mounted into Flask,
workspace, or Celery/Beat. Never touches application tables or DBA endpoints.
"""
from __future__ import annotations

import base64
import os
import secrets
import stat
from pathlib import Path
from urllib.parse import quote

ROOT = Path('/workspace')
APP_ENV = ROOT / '.env'
ADMIN_DIR = Path('/run/kaori-admin')
MIGRATOR_DIR = Path('/run/kaori-migrator')
ADMIN_SECRET = ADMIN_DIR / 'postgres_password'
RUNTIME_SECRET = ADMIN_DIR / 'runtime_password'
MIGRATOR_SECRET = MIGRATOR_DIR / 'password'
ROLE_SECRETS = (ADMIN_SECRET, RUNTIME_SECRET, MIGRATOR_SECRET)
# postgres:16 (Debian) runs its initdb scripts as the postgres OS user.
# Keep 0600 files readable to PostgreSQL without allowing a world/group ACL.
POSTGRES_UID = 999
POSTGRES_GID = 999
_PLACEHOLDER = 'postgresql://kaori_runtime:generated-by-devcontainer-initialize-command@db:5432/kaori'


def fail(message: str) -> None:
    raise SystemExit(f'KAORI DevContainer PostgreSQL: ABORT: {message}')


def env_values(source: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in source.splitlines():
        if line and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def set_value(source: str, key: str, value: str) -> str:
    lines = [line for line in source.splitlines() if not line.startswith(f'{key}=')]
    lines.append(f'{key}={value}')
    return '\n'.join(lines) + '\n'


def drop_value(source: str, key: str) -> str:
    return '\n'.join(line for line in source.splitlines() if not line.startswith(f'{key}=')) + '\n'


def write_private(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(value)
    os.chown(path, POSTGRES_UID, POSTGRES_GID)
    path.chmod(0o600)


def verify_private_volumes() -> None:
    for directory in (ADMIN_DIR, MIGRATOR_DIR):
        if directory.is_symlink() or not directory.is_dir():
            fail('expected isolated Docker named secret volume is absent or symlinked')
        if directory.stat().st_uid not in (0, POSTGRES_UID):
            fail('Docker secret volume has an unexpected owner')
        # Docker creates the volume root-owned, but the postgres:16 entrypoint
        # switches to the dedicated postgres Unix user before running initdb SQL.
        os.chown(directory, POSTGRES_UID, POSTGRES_GID)
        directory.chmod(0o700)
    for path in ROLE_SECRETS:
        if path.is_symlink():
            fail('PostgreSQL password files must not be symlinks')
        if path.exists():
            if not path.is_file():
                fail('PostgreSQL password path is not a regular file')
            info = path.stat()
            if info.st_uid != POSTGRES_UID or stat.S_IMODE(info.st_mode) != 0o600:
                fail('PostgreSQL Docker volume password files must be owned by bootstrap and mode 0600')


def prepare_app_env() -> str:
    if not (ROOT / '.env.example').is_file() or not ROOT.is_dir():
        fail('workspace source is not mounted at /workspace')
    if APP_ENV.is_symlink():
        fail('application .env must not be symlinked')
    if APP_ENV.exists() and not APP_ENV.is_file():
        fail('application .env must be a regular file')
    if not APP_ENV.exists():
        # Do not create the file yet. Refuse any existing persistent
        # credentials with missing .env before making the first writes.
        return (ROOT / '.env.example').read_text(encoding='utf-8')
    return APP_ENV.read_text(encoding='utf-8')


def persist_app_env(source: str) -> None:
    # Windows NTFS/OneDrive bind mounts have Windows ACLs; POSIX modes may
    # be synthetic there. Do not impose Unix owner checks on this bind mount.
    # Linux bind mounts should retain the source directory's owner after
    # container root creates the file.
    if not APP_ENV.exists():
        fd = os.open(APP_ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(source)
        try:
            uid, gid = ROOT.stat().st_uid, ROOT.stat().st_gid
            os.chown(APP_ENV, uid, gid)
        except OSError:
            pass  # Docker Desktop Windows binds enforce Windows ACLs instead.
    else:
        APP_ENV.write_text(source, encoding='utf-8')
    try:
        APP_ENV.chmod(0o600)
    except OSError:
        pass  # Existing Windows ACL governs this host-side file.


def main() -> None:
    if os.getenv('KAORI_DEV_DOCKER_INIT') != '1':
        fail('only the isolated Docker initializeCommand is authorized')
    verify_private_volumes()
    source = prepare_app_env()
    values = env_values(source)
    if values.get('APP_ENV', 'development') != 'development':
        fail('initialization is development-only; never alter production configuration')
    for key in (
        'KAORI_MIGRATOR_PASSWORD', 'KAORI_RUNTIME_PASSWORD',
        'KAORI_DB_MIGRATION_URL', 'PGPASSWORD', 'POSTGRES_PASSWORD_FILE',
    ):
        if key in values:
            fail(f'{key} must not be present in shared application .env')
    if values.get('POSTGRES_DB', 'kaori') != 'kaori':
        fail('DevContainer database name must be kaori')
    if values.get('POSTGRES_USER', 'postgres') != 'postgres':
        fail('DevContainer bootstrap PostgreSQL user must be postgres')

    existing = tuple(path.exists() for path in ROLE_SECRETS)
    if any(existing) and not all(existing):
        fail('incomplete persistent PostgreSQL secrets; recover them, never rotate')
    previously_initialized = all(existing)
    if previously_initialized and not APP_ENV.exists():
        fail('existing PostgreSQL secrets but missing app .env; restore it')
    current_url = values.get('DATABASE_URL', '')
    if not previously_initialized and current_url and current_url != _PLACEHOLDER:
        fail('application DB URL exists without PostgreSQL secrets; manual recovery required')

    if not previously_initialized:
        write_private(ADMIN_SECRET, secrets.token_urlsafe(36))
        write_private(RUNTIME_SECRET, secrets.token_urlsafe(36))
        write_private(MIGRATOR_SECRET, secrets.token_urlsafe(36))
        print('KAORI DevContainer: generated three role credentials in separate private Docker volumes')

    runtime_password = RUNTIME_SECRET.read_text(encoding='utf-8').strip()
    if not runtime_password:
        fail('persisted runtime credential is missing')
    runtime_url = f'postgresql://kaori_runtime:{quote(runtime_password, safe="")}@db:5432/kaori'
    if previously_initialized and current_url != runtime_url:
        fail('runtime URL does not match persistent secret; refusing to rotate or overwrite')

    source = drop_value(source, 'POSTGRES_PASSWORD')
    source = drop_value(source, 'KAORI_DEV_RUNTIME_DATABASE_URL')
    source = set_value(source, 'POSTGRES_DB', 'kaori')
    source = set_value(source, 'POSTGRES_USER', 'postgres')
    source = set_value(source, 'DATABASE_URL', runtime_url)
    if not values.get('SECRET_KEY') or values['SECRET_KEY'].startswith('replace-'):
        if previously_initialized:
            fail('existing PostgreSQL credentials with missing application SECRET_KEY')
        source = set_value(source, 'SECRET_KEY', secrets.token_urlsafe(48))
    if not values.get('INTEGRATION_CREDENTIAL_KEY'):
        if previously_initialized:
            fail('existing PostgreSQL credentials with missing application integration key')
        source = set_value(
            source, 'INTEGRATION_CREDENTIAL_KEY',
            base64.urlsafe_b64encode(os.urandom(32)).decode(),
        )
    if not values.get('ADMIN_PASSWORD') or values['ADMIN_PASSWORD'].startswith('replace-'):
        if previously_initialized:
            fail('existing PostgreSQL credentials with missing first-admin password')
        source = set_value(source, 'ADMIN_PASSWORD', secrets.token_urlsafe(32))
    if not APP_ENV.exists() or source != APP_ENV.read_text(encoding='utf-8'):
        persist_app_env(source)
    print('KAORI DevContainer: restricted DATABASE_URL prepared; postgres/migrator secrets excluded from application env')
    print('KAORI DevContainer: Alembic and first KAORI administrator require explicit operator bootstrap')


if __name__ == '__main__':
    main()
