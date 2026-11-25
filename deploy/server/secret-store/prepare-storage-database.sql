-- #5202: explicit, one-time DBA preparation, never part of unattended deploy.
-- Run from the maintenance database postgres, after target isolation approval.
-- Does not set passwords, touch the application database, or clean up existing state.
\set ON_ERROR_STOP on
\if :{?kaori_secret_store_prepare}
    \if :kaori_secret_store_prepare
    \else
        DO $$ BEGIN RAISE EXCEPTION 'Explicit Secret Store preparation opt-in required'; END $$;
    \endif
\else
    DO $$ BEGIN RAISE EXCEPTION 'Explicit Secret Store preparation opt-in required'; END $$;
\endif
SET lock_timeout = '5s';
SET statement_timeout = '60s';
DO $guard$
BEGIN
    IF current_database() <> 'postgres' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'Expected primary maintenance database postgres';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper) THEN
        RAISE EXCEPTION 'Expected independently authorized PostgreSQL administrator';
    END IF;
END
$guard$;
-- Session-scoped lock; automatically released on disconnect or failure.
SELECT pg_advisory_lock(5202, 1);
BEGIN;
DO $guard$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'kaori_secret_store')
        OR EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname IN ('kaori_secret_store_owner', 'kaori_secret_store')
        ) THEN
        RAISE EXCEPTION 'Existing Secret Store database or role; inspect and reconcile independently';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'kaori')
        OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_runtime')
        OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_migrator') THEN
        RAISE EXCEPTION 'Canonical application database identities must exist first';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_database d
        CROSS JOIN LATERAL aclexplode(COALESCE(d.datacl, acldefault('d', d.datdba))) a
        WHERE d.datname = 'kaori' AND a.grantee = 0 AND a.privilege_type = 'CONNECT'
    ) THEN
        RAISE EXCEPTION 'Application database permits PUBLIC CONNECT; no application ACL will be changed';
    END IF;
END
$guard$;
CREATE ROLE kaori_secret_store_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
-- Runtime cannot log in until the DBA provisions credentials and explicitly enables it.
CREATE ROLE kaori_secret_store NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD NULL;
COMMIT;
-- CREATE DATABASE cannot run inside a transaction. Keep access disabled until ACL verification.
CREATE DATABASE kaori_secret_store OWNER kaori_secret_store_owner ALLOW_CONNECTIONS false;
BEGIN;
REVOKE ALL ON DATABASE kaori_secret_store FROM PUBLIC;
GRANT CONNECT ON DATABASE kaori_secret_store TO kaori_secret_store;
DO $verify$
BEGIN
    IF has_database_privilege('kaori_secret_store', 'kaori', 'CONNECT')
        OR has_database_privilege('kaori_runtime', 'kaori_secret_store', 'CONNECT')
        OR has_database_privilege('kaori_migrator', 'kaori_secret_store', 'CONNECT')
        OR NOT has_database_privilege('kaori_secret_store', 'kaori_secret_store', 'CONNECT')
        OR has_database_privilege('kaori_secret_store', 'kaori_secret_store', 'CREATE')
        OR has_database_privilege('kaori_secret_store', 'kaori_secret_store', 'TEMPORARY') THEN
        RAISE EXCEPTION 'Dedicated database ACL verification failed';
    END IF;
END
$verify$;
ALTER DATABASE kaori_secret_store ALLOW_CONNECTIONS true;
COMMIT;
SELECT pg_advisory_unlock(5202, 1);
\echo PASS: dedicated database and NOLOGIN identities prepared; credential, schema and TLS admission pending
