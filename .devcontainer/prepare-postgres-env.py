#!/usr/bin/env python3
"""Host-only, idempotent DevContainer secret preparation for a *new* local DB.

Runs through devcontainer initializeCommand before Docker Compose creates services.
No database connection and no privileged secret is passed to application containers.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import stat
import subprocess
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
APP_ENV = ROOT / '.env'
SECRET_DIR = Path.home() / '.config' / 'kaori' / 'devcontainer'
DB_SECRETS = SECRET_DIR / 'postgres-bootstrap.env'
MIGRATOR_SECRETS = SECRET_DIR / 'postgres-migrate.env'


def fail(message: str) -> None:
    raise SystemExit(f'KAORI DevContainer PostgreSQL: ABORT: {message}')


def database_volume_exists() -> bool:
    """Distinguish an actually absent DevContainer volume from Docker errors.

    Never regenerate database credentials after an inspect failure or adopt a
    named volume not owned by the expected Compose project and logical key.
    """
    volume_name = 'kaori-dev_kaori_postgres_data'
    try:
        result = subprocess.run(
            ['docker', 'volume', 'inspect', volume_name],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        fail('Docker is required to check the existing local PostgreSQL volume')
    if result.returncode:
        if 'no such volume' in result.stderr.lower():
            return False
        fail('Docker volume inspection failed; refusing to assume a fresh database')
    try:
        volumes = json.loads(result.stdout)
        info, = volumes
        labels = info.get('Labels') or {}
    except (ValueError, TypeError, AttributeError):
        fail('Malformed Docker volume inspection; refusing first-run provisioning')
    if (
        info.get('Name') != volume_name
        or labels.get('com.docker.compose.project') != 'kaori-dev'
        or labels.get('com.docker.compose.volume') != 'kaori_postgres_data'
    ):
        fail('PostgreSQL volume identity/ownership differs from kaori-dev')
    return True


def existing_values(source: str) -> dict[str, str]:
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


def write_private(path: Path, content: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)


def verify_private_paths() -> None:
    """Prevent following external-secret symlinks or adopting world-readable files."""
    if APP_ENV.is_symlink():
        fail('application .env must not be a symlink')
    if APP_ENV.exists():
        if not APP_ENV.is_file() or APP_ENV.stat().st_uid != os.getuid():
            fail('application .env must be a developer-owned regular file')
        # Preserve existing settings, but never leave the runtime DB secret
        # readable by other host users after VS Code initializes.
        if stat.S_IMODE(APP_ENV.stat().st_mode) != 0o600:
            APP_ENV.chmod(0o600)
    if SECRET_DIR.is_symlink() or SECRET_DIR.resolve().is_relative_to(ROOT.resolve()):
        fail('PostgreSQL secrets directory must be outside the source workspace')
    if SECRET_DIR.exists():
        if not SECRET_DIR.is_dir():
            fail('PostgreSQL secrets path is not a directory')
        info = SECRET_DIR.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            fail('PostgreSQL secret directory must be owned by developer and mode 0700')
    for path in (DB_SECRETS, MIGRATOR_SECRETS):
        if path.is_symlink():
            fail('PostgreSQL credential files must not be symlinks')
        if path.exists():
            if not path.is_file():
                fail('PostgreSQL credential path is not a file')
            info = path.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                fail('PostgreSQL credential files must be developer-owned and mode 0600')


def main() -> None:
    verify_private_paths()
    if not APP_ENV.exists():
        if database_volume_exists():
            fail('application .env is missing for an existing database; restore it, do not rotate encryption/admin secrets')
        APP_ENV.write_text((ROOT / '.env.example').read_text(encoding='utf-8'), encoding='utf-8')
        APP_ENV.chmod(0o600)
        print('KAORI DevContainer: created private .env from .env.example')

    source = APP_ENV.read_text(encoding='utf-8')
    values = existing_values(source)
    if database_volume_exists():
        for key in ('SECRET_KEY', 'INTEGRATION_CREDENTIAL_KEY', 'ADMIN_PASSWORD'):
            if not values.get(key) or values[key].startswith('replace-'):
                fail(f'{key} missing for existing database; restore the original secret, do not regenerate')
    if values.get('POSTGRES_DB', 'kaori') != 'kaori':
        fail('local DB must be kaori; do not target another environment')
    if values.get('KAORI_DB_MIGRATION_URL'):
        fail('do not persist KAORI_DB_MIGRATION_URL in the application .env')
    if DB_SECRETS.exists() != MIGRATOR_SECRETS.exists():
        fail('only one bootstrap secret file exists; restore the matched pair, do not rotate')
    first_secrets = not DB_SECRETS.exists()
    if first_secrets and database_volume_exists():
        fail('PostgreSQL volume exists but bootstrap credentials are missing; recover credentials, do not rotate an existing database')

    if first_secrets:
        SECRET_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(SECRET_DIR, 0o700)
        postgres_password = secrets.token_urlsafe(36)
        runtime_password = secrets.token_urlsafe(36)
        migrator_password = secrets.token_urlsafe(36)
        write_private(
            DB_SECRETS,
            f'POSTGRES_PASSWORD={postgres_password}\n'
            f'KAORI_RUNTIME_PASSWORD={runtime_password}\n',
        )
        write_private(MIGRATOR_SECRETS, f'KAORI_MIGRATOR_PASSWORD={migrator_password}\n')
        print('KAORI DevContainer: generated private PostgreSQL credentials outside the repository')

    runtime = existing_values(DB_SECRETS.read_text(encoding='utf-8')).get('KAORI_RUNTIME_PASSWORD')
    if not runtime:
        fail('runtime password missing from bootstrap secret file')
    runtime_url = f'postgresql://kaori_runtime:{quote(runtime, safe="")}@db:5432/kaori'
    old_url = values.get('DATABASE_URL', '')
    if database_volume_exists() and old_url and old_url != runtime_url:
        fail('runtime DATABASE_URL differs from existing volume secrets; correct configuration before startup')

    source = drop_value(source, 'POSTGRES_PASSWORD')
    source = drop_value(source, 'KAORI_DEV_RUNTIME_DATABASE_URL')
    source = set_value(source, 'POSTGRES_DB', 'kaori')
    source = set_value(source, 'POSTGRES_USER', 'postgres')
    source = set_value(source, 'DATABASE_URL', runtime_url)
    # These are first-run development conveniences, not production credentials.
    if values.get('SECRET_KEY', '').startswith('replace-') or not values.get('SECRET_KEY'):
        source = set_value(source, 'SECRET_KEY', secrets.token_urlsafe(48))
    if not values.get('INTEGRATION_CREDENTIAL_KEY'):
        source = set_value(source, 'INTEGRATION_CREDENTIAL_KEY', base64.urlsafe_b64encode(os.urandom(32)).decode())
    if values.get('ADMIN_PASSWORD', '').startswith('replace-') or not values.get('ADMIN_PASSWORD'):
        source = set_value(source, 'ADMIN_PASSWORD', secrets.token_urlsafe(32))
    if source != APP_ENV.read_text(encoding='utf-8'):
        APP_ENV.write_text(source, encoding='utf-8')
        APP_ENV.chmod(0o600)
    print('KAORI DevContainer: runtime URL configured; privileged DB credentials are DB/bootstrap-only')
    print('KAORI DevContainer: first-run administration password is in private .env (ADMIN_PASSWORD)')


if __name__ == '__main__':
    main()
