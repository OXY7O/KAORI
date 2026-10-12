#!/usr/bin/env python3
"""One-time, non-destructive recovery of DevContainer #1499 Docker role secrets.

Executed manually in a short-lived Docker Python container FROM WINDOWS
POWERSHELL. The two old named volumes and existing PostgreSQL data are mounted
read-only; only the repository's ignored secrets/devcontainer/ files are written.

Never creates PostgreSQL users, connects to/mutates PostgreSQL, changes the
application DATABASE_URL, rotates a password or removes a Docker volume.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path("/workspace")
APP_ENV = ROOT / ".env"
PG_DATA = Path("/pgdata")
LEGACY_ADMIN = Path("/legacy-admin")
LEGACY_MIGRATOR = Path("/legacy-migrator")
SECRET_DIR = ROOT / "secrets" / "devcontainer"
ADMIN_DEST = SECRET_DIR / "postgres-bootstrap.env"
MIGRATOR_DEST = SECRET_DIR / "postgres-migrate.env"
_LOCAL_ROLE_PASSWORD = re.compile(r"^[A-Za-z0-9_-]{16,}$")


def abort(message: str) -> None:
    raise SystemExit(f"KAORI DevContainer legacy secret recovery: ABORT: {message}")


def read_secret(filename: Path) -> str:
    if filename.is_symlink() or not filename.is_file():
        abort("a legacy Docker credential file is missing or symlinked")
    try:
        credential = filename.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        abort("cannot read a legacy Docker credential file")
    if not _LOCAL_ROLE_PASSWORD.fullmatch(credential):
        abort("a legacy Docker credential does not match the generated role-secret format")
    return credential


def read_config_value(source: str, name: str) -> str:
    entries = [
        line.split("=", 1)[1].strip()
        for line in source.splitlines()
        if line.startswith(f"{name}=")
    ]
    if len(entries) != 1:
        abort(f"application .env must contain exactly one {name}")
    return entries[0]


def check_paths() -> None:
    for directory in (ROOT / "secrets", SECRET_DIR):
        if directory.is_symlink():
            abort("secrets directory is a symlink")
        if directory.exists() and not directory.is_dir():
            abort("secrets directory is not a directory")
    for destination in (ADMIN_DEST, MIGRATOR_DEST):
        if destination.is_symlink():
            abort("a local credential destination is a symlink")
        if destination.exists() and not destination.is_file():
            abort("a local credential destination is not a regular file")


def ensure_existing_or_create(destination: Path, expected: str) -> bool:
    """Create missing destination exclusively; keep existing files unchanged."""
    if destination.exists():
        existing = destination.read_text(encoding="utf-8")
        if existing != expected:
            abort("an existing ignored credential file does not match the legacy volume")
        return False
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(expected)
    try:
        destination.chmod(0o600)
    except OSError:
        # Docker Desktop bind mounts on Windows enforce host ACLs.
        pass
    return True


def main() -> int:
    if os.environ.get("KAORI_DEV_LEGACY_RECOVERY") != "1":
        abort("run only the explicit operator legacy recovery Docker command")
    if not (ROOT / ".env.example").is_file():
        abort("KAORI repository is not mounted at /workspace")
    if not PG_DATA.is_dir() or not (PG_DATA / "PG_VERSION").is_file():
        abort("initialized PostgreSQL data volume is missing; no legacy recovery permitted")
    if (PG_DATA / "PG_VERSION").read_text(encoding="utf-8").strip() != "16":
        abort("legacy PostgreSQL major version is not the approved bundled version")
    if APP_ENV.is_symlink() or not APP_ENV.is_file():
        abort("private app .env is missing or symlinked; recover it before secrets")
    app_text = APP_ENV.read_text(encoding="utf-8")
    if read_config_value(app_text, "APP_ENV") != "development":
        abort("recovery is development-only")

    check_paths()
    admin_password = read_secret(LEGACY_ADMIN / "postgres_password")
    runtime_password = read_secret(LEGACY_ADMIN / "runtime_password")
    migrator_password = read_secret(LEGACY_MIGRATOR / "password")
    if len({admin_password, runtime_password, migrator_password}) != 3:
        abort("legacy PostgreSQL role passwords are not distinct")
    expected_runtime = (
        "postgresql://kaori_runtime:"
        + quote(runtime_password, safe="")
        + "@db:5432/kaori"
    )
    if read_config_value(app_text, "DATABASE_URL") != expected_runtime:
        abort("app runtime DATABASE_URL differs from the legacy volume secret; no files changed")

    bootstrap_env = (
        f"POSTGRES_PASSWORD={admin_password}\n"
        f"KAORI_RUNTIME_PASSWORD={runtime_password}\n"
    )
    migration_env = f"KAORI_MIGRATOR_PASSWORD={migrator_password}\n"
    # Validate both destinations before writing either file.
    for path, contents in ((ADMIN_DEST, bootstrap_env), (MIGRATOR_DEST, migration_env)):
        if path.exists() and path.read_text(encoding="utf-8") != contents:
            abort("existing ignored PostgreSQL ENV differs from the legacy secret volume")

    SECRET_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    created_bootstrap = ensure_existing_or_create(ADMIN_DEST, bootstrap_env)
    created_migration = ensure_existing_or_create(MIGRATOR_DEST, migration_env)

    print("PASS: local PostgreSQL credential ENV matches the legacy Docker volumes")
    print(
        "Recovery: "
        + ("created" if created_bootstrap else "validated")
        + " postgres-bootstrap.env and "
        + ("created" if created_migration else "validated")
        + " postgres-migrate.env"
    )
    print("Database, Docker volumes and application .env were not modified.")
    print("Next: retry VS Code Windows Dev Containers: Rebuild and Reopen in Container.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
