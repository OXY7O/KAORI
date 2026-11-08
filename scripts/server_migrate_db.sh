#!/bin/sh
set -eu

# Server-only, one-shot migration. Never use the ordinary runtime login for DDL.
[ "${APP_ENV:-}" = production ] || {
  echo 'ABORT: server migration requires production identity' >&2
  exit 1
}
[ -n "${KAORI_DB_MIGRATION_URL:-}" ] || {
  echo 'ABORT: dedicated migration credential is missing' >&2
  exit 1
}

# Check both target identity and ownership before invoking any Alembic DDL.
python scripts/server_database_boundary.py migrator

# Override DATABASE_URL solely for this foreground Alembic subprocess.
# The normal web/worker/Beat containers never mount this migration credential.
DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade

# Newly created tables intentionally receive no blanket default privileges.
# Refresh grants only after a successful migration; immutable ledger and
# Alembic version write restrictions are checked in the same transaction.
python scripts/server_database_boundary.py grant
