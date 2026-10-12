#!/bin/sh
set -eu

# #1427: Alembic runs only as non-superuser kaori_migrator.
# Runtime DATABASE_URL stays exclusively kaori_runtime for Flask and workers.
# This script never creates PostgreSQL roles or uses the postgres superuser.
if [ -z "${KAORI_DB_MIGRATION_URL:-}" ]; then
    echo "A temporary KAORI_DB_MIGRATION_URL (kaori_migrator) is required." >&2
    echo "Do not run database migrations with kaori_runtime." >&2
    exit 1
fi

if [ "${1:-}" = "--bootstrap-admin" ]; then
    echo "ABORT: use the explicit DevContainer initialize_database task for first-admin setup." >&2
    exit 1
fi

# Fail before any schema write if the selected identity is not the
# DevContainer schema migrator or is the ordinary application runtime.
# This check uses the SAME migration connection Alembic will use.
python - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

migration_dsn = os.environ["KAORI_DB_MIGRATION_URL"]
runtime_dsn = os.getenv("DATABASE_URL", "")
expected_owner = 'kaori_migrator'
expected_database = 'kaori'
migration = make_url(migration_dsn)

if migration.username != expected_owner or migration.database != expected_database:
    print("ABORT: migration identity/database differs from DevContainer bootstrap authority.", file=sys.stderr)
    sys.exit(1)
if runtime_dsn:
    runtime = make_url(runtime_dsn)
    if migration.username == runtime.username:
        print("ABORT: migration and application identities must differ.", file=sys.stderr)
        sys.exit(1)
    if migration.host != runtime.host or migration.database != runtime.database:
        print("ABORT: migration and runtime connections target different databases.", file=sys.stderr)
        sys.exit(1)

try:
    with create_engine(migration_dsn).connect() as connection:
        actual_owner, actual_database = connection.execute(
            text("SELECT current_user, current_database()")
        ).one()
except Exception:
    print("ABORT: cannot authenticate/connect using the declared migration identity.", file=sys.stderr)
    sys.exit(1)
if actual_owner != expected_owner or actual_database != expected_database:
    print("ABORT: PostgreSQL effective migration identity/database mismatch.", file=sys.stderr)
    sys.exit(1)

with create_engine(migration_dsn).connect() as connection:
    flags = connection.execute(text(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname = current_user"
    )).one()
    owned = connection.execute(text(
        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'kaori'"
    )).scalar()
    can_create = connection.execute(text(
        "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
    )).scalar()
if any(flags) or owned != expected_owner or not can_create:
    print("ABORT: migration principal is elevated or lacks approved schema ownership.", file=sys.stderr)
    sys.exit(1)
print("PASS: explicit DevContainer PostgreSQL migration identity admitted")
PY

DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade

# RBAC seed is migration-owned data. Application administrator is created
# AFTER runtime grants, by the explicit initialize_database.py workflow.
DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac
echo "Database migration and RBAC initialization completed."
