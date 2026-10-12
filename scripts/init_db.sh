#!/bin/sh
set -eu

# #1427: migration authority is NEVER the normal DATABASE_URL application login.
# The one-off DevContainer migration runner supplies this protected ephemeral URL.
if [ -z "${KAORI_DB_MIGRATION_URL:-}" ]; then
    echo 'ABORT: KAORI_DB_MIGRATION_URL is required for Alembic; do not migrate as application runtime.' >&2
    exit 1
fi

python - <<'PY'
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

migration_url = make_url(os.environ['KAORI_DB_MIGRATION_URL'])
runtime_url = make_url(os.environ['DATABASE_URL'])
if (migration_url.username != 'kaori_migrator'
        or runtime_url.username != 'kaori_runtime'
        or migration_url.host != runtime_url.host
        or migration_url.database != runtime_url.database
        or migration_url.database != 'kaori'):
    sys.exit('ABORT: development migration target or role differs from the restricted runtime database')
try:
    with create_engine(migration_url).connect() as conn:
        row = conn.execute(text("""
            SELECT current_user, current_database(),
                   rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
            FROM pg_roles WHERE rolname = current_user
        """)).one()
except Exception:
    sys.exit('ABORT: migration identity connection failed (credentials not printed)')
if row[0] != 'kaori_migrator' or row[1] != 'kaori' or any(row[2:]):
    sys.exit('ABORT: migration must run as non-elevated kaori_migrator against local kaori database')
print('PASS: trusted, non-superuser migration identity admitted')
PY

DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app db upgrade

case "${1:-}" in
    --schema-only)
        echo 'Schema upgraded; runtime grants and application administrator bootstrap are still required.'
        ;;
    --bootstrap-admin)
        # For backward-compatible operator use, the one-shot runner should be preferred:
        # it refreshes restricted grants before creating an administrator under runtime.
        DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app bootstrap-admin
        ;;
    "")
        DATABASE_URL="$KAORI_DB_MIGRATION_URL" flask --app run:app seed-rbac
        ;;
    *)
        echo 'Usage: scripts/init_db.sh [--schema-only|--bootstrap-admin]' >&2
        exit 2
        ;;
esac
