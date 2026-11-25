-- #5202: OpenBao 2.7 PostgreSQL single-instance storage schema.
-- Execute only against the independently verified fresh dedicated database.
-- DBA creates kaori_secret_store_owner (NOLOGIN) and kaori_secret_store
-- (restricted LOGIN) and database/ACLs first. No secrets in this script.
-- https://openbao.org/docs/configuration/storage/postgresql/
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $guard$
BEGIN
    IF current_database() <> 'kaori_secret_store' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'Refusing Secret Store schema provisioning outside its primary dedicated database';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper) THEN
        RAISE EXCEPTION 'Expected independently authorized PostgreSQL administrator';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'kaori_secret_store_owner' AND NOT rolcanlogin
          AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'kaori_secret_store' AND rolcanlogin
          AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'Missing or elevated dedicated storage identities';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname <> 'kaori_secret_store'
          AND pg_has_role('kaori_secret_store', oid, 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'Secret Store runtime must not inherit other roles';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = current_database()
          AND pg_get_userbyid(datdba) = 'kaori_secret_store_owner'
    ) THEN
        RAISE EXCEPTION 'Unexpected Secret Store database ownership';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_stat_activity WHERE datname = current_database()
          AND pid <> pg_backend_pid()
    ) THEN
        RAISE EXCEPTION 'Other sessions remain; stop Secret Store before provisioning';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_namespace
        WHERE nspname NOT IN ('public', 'information_schema') AND left(nspname, 3) <> 'pg_'
    ) OR EXISTS (
        SELECT 1 FROM pg_class WHERE relnamespace = 'public'::regnamespace
    ) OR EXISTS (
        SELECT 1 FROM pg_proc WHERE pronamespace = 'public'::regnamespace
    ) OR EXISTS (
        SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql'
    ) THEN
        RAISE EXCEPTION 'Existing schema objects detected; refuse repeat or populated-state provisioning';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = 'kaori'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kaori_runtime'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kaori_migrator'
    ) THEN
        RAISE EXCEPTION 'Canonical KAORI database identities must be provisioned first';
    END IF;
    IF has_database_privilege('kaori_secret_store', 'kaori', 'CONNECT') THEN
        RAISE EXCEPTION 'Secret Store runtime can connect to application database';
    END IF;
END
$guard$;
-- Only mutate the verified empty dedicated database, never kaori.
REVOKE ALL ON DATABASE kaori_secret_store FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO kaori_secret_store_owner;
GRANT CONNECT ON DATABASE kaori_secret_store TO kaori_secret_store;
GRANT USAGE ON SCHEMA public TO kaori_secret_store;
SET LOCAL ROLE kaori_secret_store_owner;
CREATE TABLE public.openbao_kv_store (
    parent_path TEXT COLLATE "C" NOT NULL,
    path TEXT COLLATE "C",
    key TEXT COLLATE "C",
    value BYTEA,
    CONSTRAINT openbao_kv_store_pkey PRIMARY KEY (path, key)
);
CREATE INDEX openbao_kv_store_idx ON public.openbao_kv_store (parent_path);
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.openbao_kv_store TO kaori_secret_store;
RESET ROLE;
DO $verify$
BEGIN
    IF has_database_privilege('kaori_runtime', current_database(), 'CONNECT')
        OR has_database_privilege('kaori_migrator', current_database(), 'CONNECT')
        OR has_database_privilege('kaori_secret_store', current_database(), 'CREATE')
        OR has_database_privilege('kaori_secret_store', current_database(), 'TEMPORARY')
        OR has_schema_privilege('kaori_secret_store', 'public', 'CREATE')
        OR has_table_privilege('kaori_secret_store', 'public.openbao_kv_store', 'TRUNCATE')
        OR has_table_privilege('kaori_secret_store', 'public.openbao_kv_store', 'TRIGGER') THEN
        RAISE EXCEPTION 'Storage boundary ACL verification failed';
    END IF;
END
$verify$;
COMMIT;
\echo PASS: dedicated Secret Store schema provisioned; TLS and runtime admission still required
