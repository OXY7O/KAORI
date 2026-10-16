-- Explicit bundled PostgreSQL role preparation (#1439). ADMINISTRATOR ONLY.
-- Creates missing NOLOGIN restricted roles; changes no data/DB ownership.
-- Does NOT set any passwords or enable LOGIN. A separate reviewed and
-- backed-up ownership cutover is mandatory before server migration admission.
\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE
    v_admin record;
    v_runtime record;
    v_migrator record;
BEGIN
    IF current_database() <> 'kaori' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'Refusing role creation outside primary kaori database';
    END IF;
    SELECT rolsuper, rolcreatedb, rolcreaterole
      INTO v_admin FROM pg_roles WHERE rolname = current_user;
    IF v_admin.rolsuper IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Bundled role initialization requires trusted PostgreSQL admin';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_migrator') THEN
        CREATE ROLE kaori_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_runtime') THEN
        CREATE ROLE kaori_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS NOINHERIT;
    END IF;
    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
      INTO v_migrator FROM pg_roles WHERE rolname = 'kaori_migrator';
    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
      INTO v_runtime FROM pg_roles WHERE rolname = 'kaori_runtime';
    IF v_migrator.rolsuper OR v_migrator.rolcreatedb OR v_migrator.rolcreaterole
       OR v_migrator.rolreplication OR v_migrator.rolbypassrls
       OR v_runtime.rolsuper OR v_runtime.rolcreatedb OR v_runtime.rolcreaterole
       OR v_runtime.rolreplication OR v_runtime.rolbypassrls
       OR pg_has_role('kaori_runtime', 'kaori_migrator', 'MEMBER')
    THEN
        RAISE EXCEPTION 'Existing role is elevated or runtime inherits migration authority';
    END IF;
END $$;
COMMIT;
-- Operator next: use interactive psql \password separately on each role,
-- then ALTER ROLE ... LOGIN; once private host-only credentials are installed.
