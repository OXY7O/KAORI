-- DevContainer PostgreSQL grant refresh under restricted kaori_migrator.
-- postgres bootstrap owns role creation ONLY on the empty-volume one-shot.
-- This is an explicit operator migration step; not part of app startup.
-- Non-superuser kaori_migrator owns all Alembic-created application tables.
-- No blanket default ACLs: new immutable tables must be reviewed first.
-- Credentials never appear in this committed SQL file.

\set ON_ERROR_STOP on
\if :{?kaori_devcontainer_confirm}
\else
\echo 'Explicit -v kaori_devcontainer_confirm=1 required; aborting.'
\quit 3
\endif

BEGIN;
DO $$
DECLARE
    -- CURRENT_ROLE is a PostgreSQL SQL special form, not a safe record name.
    v_role_flags record;
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

    IF current_user <> 'kaori_migrator'
       OR NOT has_schema_privilege(current_user, 'public', 'CREATE')
       OR pg_get_userbyid((
           SELECT relowner FROM pg_class
           WHERE oid = 'public.capsule_handoff_ledger_events'::regclass
       )) <> current_user
    THEN
        RAISE EXCEPTION 'Trusted non-superuser schema migrator/ledger owner required';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_runtime') THEN
        RAISE EXCEPTION 'Restricted runtime principal must be provisioned before migrations';
    END IF;

    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
    INTO v_role_flags FROM pg_roles WHERE rolname = 'kaori_runtime';
    IF v_role_flags.rolsuper OR v_role_flags.rolcreatedb
       OR v_role_flags.rolcreaterole OR v_role_flags.rolreplication
       OR v_role_flags.rolbypassrls
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

-- Never rotate credentials or change LOGIN from a schema migration;
-- the one-shot bootstrap has already provisioned the application principal.
