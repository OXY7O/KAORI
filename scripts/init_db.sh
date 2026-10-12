#!/bin/sh
set -eu

# Database DDL/RBAC bootstrap remains owner-only after the DevContainer
# application and workers switch to a non-owner runtime login. The owner
# connection must be supplied only for this command, not stored in the
# environment file loaded by Celery workers.
if [ -n "${KAORI_DEV_RUNTIME_DATABASE_URL:-}" ] && [ -z "${KAORI_DB_MIGRATION_URL:-}" ]; then
    echo "KAORI DevContainer runtime DB role is active. Supply a temporary" >&2
    echo "KAORI_DB_MIGRATION_URL using the migration/owner account." >&2
    echo "Do not run database migrations with kaori_runtime." >&2
    exit 1
fi

if [ -n "${KAORI_DB_MIGRATION_URL:-}" ]; then
    DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade
else
    flask --app run:app db upgrade
fi

if [ "${1:-}" = "--bootstrap-admin" ]; then
    # bootstrap-admin seeds the default RBAC catalog before creating the user.
    if [ -n "${KAORI_DB_MIGRATION_URL:-}" ]; then
        DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app bootstrap-admin
    else
        flask --app run:app bootstrap-admin
    fi
else
    if [ -n "${KAORI_DB_MIGRATION_URL:-}" ]; then
        DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac
    else
        flask --app run:app seed-rbac
    fi
fi

echo "Database migration and RBAC initialization completed."

if [ "${1:-}" != "--bootstrap-admin" ]; then
    echo "Run 'flask --app run:app bootstrap-admin' when the first administrator is required."
fi
