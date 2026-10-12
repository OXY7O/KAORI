-- #1427: apply AFTER Alembic upgrade, by kaori_migrator (never runtime).
-- This is an explicit migration-stage grant refresh, NOT default privileges.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF current_database() <> 'kaori'
        OR current_user <> 'kaori_migrator'
        OR current_setting('application_name', true) <> 'kaori-devcontainer-runtime-grants'
        OR pg_is_in_recovery()
    THEN
        RAISE EXCEPTION 'Wrong database, role or application_name for KAORI DevContainer grants';
    END IF;
    IF to_regclass('public.capsule_handoff_ledger_events') IS NULL
        OR to_regclass('public.audit_events') IS NULL
        OR to_regclass('public.alembic_version') IS NULL
    THEN
        RAISE EXCEPTION 'Alembic schema and immutable ledger must exist before role grants';
    END IF;
    IF (SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
        FROM pg_roles WHERE rolname = 'kaori_runtime')
        OR pg_has_role('kaori_runtime', 'kaori_migrator', 'MEMBER')
        OR has_schema_privilege('kaori_runtime', 'public', 'CREATE')
    THEN
        RAISE EXCEPTION 'Runtime role elevated before grant refresh';
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kaori_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO kaori_runtime;
-- START ledger must never inherit blanket mutation privileges.
REVOKE ALL PRIVILEGES ON TABLE public.capsule_handoff_ledger_events FROM kaori_runtime;
GRANT SELECT, INSERT ON TABLE public.capsule_handoff_ledger_events TO kaori_runtime;

DO $$
BEGIN
    IF has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'UPDATE')
        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'DELETE')
        OR has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'TRUNCATE')
        OR NOT has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'SELECT')
        OR NOT has_table_privilege('kaori_runtime', 'public.capsule_handoff_ledger_events', 'INSERT')
        OR has_schema_privilege('kaori_runtime', 'public', 'CREATE')
        OR has_table_privilege('kaori_runtime', 'public.audit_events', 'TRUNCATE')
    THEN
        RAISE EXCEPTION 'Runtime immutable-ledger privileges denied; transaction rolled back';
    END IF;
END $$;
COMMIT;
