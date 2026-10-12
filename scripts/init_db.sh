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
