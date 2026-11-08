#!/bin/sh
set -eu

# #1528: automatic on DevContainer startup ONLY for a genuinely virgin local
# schema. Any prior object/partial migration means skip, never auto-upgrade.
if [ "${APP_ENV:-}" != development ] || [ -z "${KAORI_MIGRATOR_PASSWORD:-}" ]; then
    echo 'ABORT: dev-only auto bootstrap requires scoped migrator credential' >&2
    exit 1
fi

python - <<'PY'
import os
import sys
from sqlalchemy.engine import make_url

runtime = make_url(os.getenv('DATABASE_URL', ''))
if (runtime.username != 'kaori_runtime' or runtime.host != 'db'
        or (runtime.port or 5432) != 5432 or runtime.database != 'kaori'):
    sys.exit('ABORT: auto bootstrap requires canonical restricted DevContainer URL')
PY

# Read-only schema inspection as the migrator after PostgreSQL initdb.
# Public relations (including sequences), routines, custom types, extensions
# or custom namespaces all mean this is NOT a guaranteed virgin installation.
database_state="$(
    PGPASSWORD="$KAORI_MIGRATOR_PASSWORD" psql -w -h db -U kaori_migrator \
      -d kaori -X -A -t -v ON_ERROR_STOP=1 -c "
SELECT CASE
 WHEN current_user <> 'kaori_migrator'
   OR current_database() <> 'kaori'
   OR (SELECT pg_get_userbyid(datdba) FROM pg_catalog.pg_database
       WHERE datname = current_database()) <> 'kaori_migrator'
 THEN 'invalid'
 WHEN EXISTS (
   SELECT 1 FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','f','S')
 ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_proc p
   JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
 ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_type t
   JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
   WHERE n.nspname = 'public' AND t.typtype IN ('e','d','c','r','m')
 ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_namespace n
   WHERE n.nspname NOT IN ('public', 'pg_catalog', 'information_schema')
     AND n.nspname NOT LIKE 'pg_toast%'
     AND n.nspname NOT LIKE 'pg_temp_%'
 ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql'
 ) THEN 'existing'
 ELSE 'virgin'
 END;"
)" || {
    echo 'ABORT: cannot inspect schema; no automatic migration' >&2
    exit 1
}
case "$database_state" in
    virgin)
        echo 'KAORI DevContainer: virgin schema verified; running one-shot bootstrap'
        exec sh scripts/devcontainer/bootstrap-db.sh
        ;;
    existing)
        echo 'KAORI DevContainer: existing/partial schema detected; No automatic migration'
        ;;
    *)
        echo 'ABORT: unexpected database role/state; no automatic migration' >&2
        exit 1
        ;;
esac
