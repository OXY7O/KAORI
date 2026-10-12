#!/bin/sh
set -eu

# #1427: one canonical non-owner DATABASE_URL serves Flask/Celery/Beat.
# Schema migrations, RBAC seed and bootstrap-admin are owner-only operations.
# Never inherit the application runtime URL for DDL or persist the owner URL
# in .env (the latter is passed to DevContainer workers and Beat).
if [ -z "${KAORI_DB_MIGRATION_URL:-}" ]; then
    echo "A temporary KAORI_DB_MIGRATION_URL (PostgreSQL owner) is required." >&2
    echo "Do not run database migrations with kaori_runtime." >&2
    exit 1
fi

# Fail before any schema write if the selected identity is not the
# DevContainer bootstrap owner or is the ordinary application runtime.
# This check uses the SAME migration connection Alembic will use.
python - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

migration_dsn = os.environ["KAORI_DB_MIGRATION_URL"]
runtime_dsn = os.getenv("DATABASE_URL", "")
expected_owner = os.getenv("POSTGRES_USER", "kaori")
expected_database = os.getenv("POSTGRES_DB", "kaori")
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
    print("ABORT: PostgreSQL effective owner or database differs from approved DevContainer target.", file=sys.stderr)
    sys.exit(1)
print("PASS: explicit DevContainer PostgreSQL migration identity admitted")
PY

DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade

if [ "${1:-}" = "--bootstrap-admin" ]; then
    # bootstrap-admin seeds the canonical RBAC catalog first.
    DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app bootstrap-admin
else
    DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac
fi

echo "Database migration and RBAC initialization completed."

if [ "${1:-}" != "--bootstrap-admin" ]; then
    echo "Run bootstrap-admin with the same temporary KAORI_DB_MIGRATION_URL when the first administrator is required."
fi
