#!/bin/sh
set -eu

# Explicit operator action (NOT part of DevContainer auto-start).
# Container identity is a one-shot DevContainer service; all web/workers/Beat
# retain only their existing canonical non-owner DATABASE_URL.
if [ "${APP_ENV:-}" != development ] || [ -z "${KAORI_MIGRATOR_PASSWORD:-}" ]; then
    echo 'ABORT: DevContainer migrator secret or development boundary unavailable' >&2
    exit 1
fi
case "${1:-}" in
    "") bootstrap_admin=true ;;
    --upgrade-only) bootstrap_admin=false ;;
    *) echo 'Usage: bootstrap-db.sh [--upgrade-only]' >&2; exit 2 ;;
esac

migration_password="$KAORI_MIGRATOR_PASSWORD"
KAORI_DB_MIGRATION_URL="$(python - <<'PY'
import os
import sys
from sqlalchemy.engine import URL, make_url
runtime = make_url(os.getenv('DATABASE_URL', ''))
if runtime.username != 'kaori_runtime' or runtime.host != 'db' or runtime.database != 'kaori':
    sys.exit('ABORT: bootstrap requires canonical restricted DevContainer runtime database')
print(URL.create(
    'postgresql',
    username='kaori_migrator',
    password=os.environ['KAORI_MIGRATOR_PASSWORD'],
    host='db',
    port=5432,
    database='kaori',
).render_as_string(hide_password=False))
PY
)" || exit 1
export KAORI_DB_MIGRATION_URL
unset KAORI_MIGRATOR_PASSWORD

# Preflight all credentials and migration identity before mutating schema.
sh scripts/init_db.sh --schema-only

# The same non-superuser schema OWNER grants DML only AFTER DDL is complete.
PGPASSWORD="$migration_password" PGAPPNAME=kaori-devcontainer-runtime-grants \
  psql -h db -U kaori_migrator -d kaori -X -v ON_ERROR_STOP=1 \
  -f scripts/devcontainer/grant_postgres_runtime.sql
unset migration_password KAORI_DB_MIGRATION_URL

# First KAORI administrator and RBAC catalog are application-domain operations.
# This Flask process uses canonical DATABASE_URL as kaori_runtime, not migrator.
if [ "$bootstrap_admin" = true ]; then
  flask --app run:app bootstrap-admin
else
  flask --app run:app seed-rbac
fi

python - <<'PY'
from run import app
from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _require_postgres_ledger_write_once_guards,
)
with app.app_context():
    assert db.engine.url.username == 'kaori_runtime'
    try:
        _require_postgres_ledger_write_once_guards(db.session)
    finally:
        db.session.rollback()
print('PASS: migrations, RBAC/admin and immutable Capsule runtime guard complete')
PY
