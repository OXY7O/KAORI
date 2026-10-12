-- KAORI DevContainer PostgreSQL application role provisioning (#1405).
-- Execute ONCE per permission refresh *after* Alembic upgrades, using the
-- trusted owner/migration connection to the existing development database.
-- This script never creates/drops databases, moves rows, or changes ownership.
-- An initial role is created NOLOGIN; set its password with interactive
-- psql \password and enable LOGIN only after reviewing the read-only checks.
--
-- Example from a trusted DevContainer terminal with owner psql connection:
--   PGAPPNAME=kaori-devcontainer-role-provision psql -h db -U kaori -W -d kaori \
--     -X -v ON_ERROR_STOP=1 -v kaori_devcontainer_confirm=1 \
--     -f scripts/devcontainer/provision_postgres_runtime_role.sql
-- Then inside interactive owner psql: \password kaori_runtime
-- Then ALTER ROLE kaori_runtime LOGIN;
--
-- The runtime login never receives ownership, CREATE, TRUNCATE or schema DDL.
-- Permissions for future tables MUST be refreshed after each Alembic upgrade:
-- no blanket ALTER DEFAULT PRIVILEGES, which could grant UPDATE/DELETE to
-- future immutable evidence ledgers.

\set ON_ERROR_STOP on
\if :{?kaori_devcontainer_confirm}
\else
\echo 'Explicit -v kaori_devcontainer_confirm=1 required; aborting.'
\quit 3
\endif

BEGIN;
DO $$
DECLARE
    current_role record;
BEGIN
    IF current_database() <> 'kaori'
       OR current_setting('application_name', true) <> 'kaori-devcontainer-role-provision'
       OR pg_is_in_recovery()
    THEN
        RAISE EXCEPTION 'Refusing runtime-role provisioning outside the explicit local kaori DevContainer database';
    END IF;
    IF to_regclass('public.capsule_handoff_ledger_events') IS NULL
       OR to_regclass('public.audit_events') IS NULL
       OR to_regclass('public.alembic_version') IS NULL
    THEN
        RAISE EXCEPTION 'Apply current KAORI schema migrations as DB owner first; existing ledger/audit tables required';
    END IF;

    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
    INTO current_role FROM pg_roles WHERE rolname = current_user;
    IF current_role.rolsuper IS DISTINCT FROM TRUE
       AND current_role.rolcreaterole IS DISTINCT FROM TRUE
    THEN
        RAISE EXCEPTION 'Trusted existing PostgreSQL owner/admin connection required';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_runtime') THEN
        CREATE ROLE kaori_runtime
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS INHERIT;
    END IF;

    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
    INTO current_role FROM pg_roles WHERE rolname = 'kaori_runtime';
    IF current_role.rolsuper OR current_role.rolcreatedb
       OR current_role.rolcreaterole OR current_role.rolreplication
       OR current_role.rolbypassrls
       OR pg_has_role(
           (SELECT oid FROM pg_roles WHERE rolname = 'kaori_runtime'),
           (SELECT relowner FROM pg_class
            WHERE oid = 'public.capsule_handoff_ledger_events'::regclass),
           'MEMBER'
       )
    THEN
        RAISE EXCEPTION 'Existing kaori_runtime role is elevated or is a member of immutable ledger owner';
    END IF;
END $$;

-- Keep existing DB/owner and data untouched. No schema CREATE or table owner.
GRANT CONNECT ON DATABASE kaori TO kaori_runtime;
GRANT USAGE ON SCHEMA public TO kaori_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO kaori_runtime;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO kaori_runtime;

-- Revoke all blanket table grants inherited from the preceding statement,
-- then add back only append-only operations needed by the START ledger.
REVOKE ALL PRIVILEGES
    ON TABLE public.capsule_handoff_ledger_events FROM kaori_runtime;
GRANT SELECT, INSERT
    ON TABLE public.capsule_handoff_ledger_events TO kaori_runtime;

-- Ensure negative privileges under the *effective* role ACL, including
-- inherited roles and PUBLIC, not merely the explicit per-role GRANT rows.
DO $$
BEGIN
    IF has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'UPDATE')
       OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'DELETE')
       OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'TRUNCATE')
       OR NOT has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'SELECT')
       OR NOT has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'INSERT')
       OR has_table_privilege('kaori_runtime', 'public.audit_events', 'TRUNCATE')
       OR has_schema_privilege('kaori_runtime', 'public', 'CREATE')
    THEN
        RAISE EXCEPTION 'Runtime role grants violate immutable evidence or schema isolation; transaction rolled back';
    END IF;
END $$;
COMMIT;

-- Never ALTER ROLE ... LOGIN with a blank password. Finish with interactive
-- \password kaori_runtime under trusted psql and then enable LOGIN separately.
