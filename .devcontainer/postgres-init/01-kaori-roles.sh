#!/bin/sh
set -eu

# PostgreSQL's official initdb entrypoint runs this ONLY for an empty data volume.
# Executed by the local database container as its bootstrap administrator.
# Never mount these DB-only environment values into Flask/Celery containers.
[ "${POSTGRES_USER:-}" = postgres ] || { echo 'ABORT: expected local postgres bootstrap user' >&2; exit 1; }
[ "${POSTGRES_DB:-}" = kaori ] || { echo 'ABORT: expected local kaori database' >&2; exit 1; }
# Bundled local PostgreSQL reads two ignored, service-scoped env files:
# postgres-bootstrap.env and postgres-migrate.env. These must never be
# loaded into Flask/Celery/Beat; no password literals are committed.
[ -n "${POSTGRES_PASSWORD:-}" ] &&
[ -n "${KAORI_RUNTIME_PASSWORD:-}" ] &&
[ -n "${KAORI_MIGRATOR_PASSWORD:-}" ] ||
  { echo 'ABORT: missing private PostgreSQL credential ENV values' >&2; exit 1; }

# Load role passwords via psql's environment-variable reader rather than
# process arguments (ps argv would otherwise disclose both secrets).
# psql quotes variables as SQL string literals for the ALTER ROLE statements.
psql -X --set=ON_ERROR_STOP=1 --username postgres --dbname kaori <<'SQL'
\getenv migrator_password KAORI_MIGRATOR_PASSWORD
\getenv runtime_password KAORI_RUNTIME_PASSWORD
CREATE ROLE kaori_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE kaori_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
SELECT format('ALTER ROLE kaori_migrator PASSWORD %L', :'migrator_password') \gexec
SELECT format('ALTER ROLE kaori_runtime PASSWORD %L', :'runtime_password') \gexec
ALTER DATABASE kaori OWNER TO kaori_migrator;
ALTER SCHEMA public OWNER TO kaori_migrator;
REVOKE ALL ON DATABASE kaori FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE kaori TO kaori_runtime;
GRANT USAGE ON SCHEMA public TO kaori_runtime;
SQL

unset KAORI_RUNTIME_PASSWORD KAORI_MIGRATOR_PASSWORD
echo 'KAORI DevContainer: database and separated PostgreSQL roles initialized; application schema remains empty'
