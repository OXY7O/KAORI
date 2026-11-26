-- #5202: read-only session verification from the dedicated runtime identity.
-- Connect using psql with explicit sslmode=verify-full and approved sslrootcert.
-- Server-side TLS evidence cannot establish the client's hostname/CA verification.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
DO $verify$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_stat_ssl WHERE pid = pg_backend_pid()
          AND ssl AND version IN ('TLSv1.2', 'TLSv1.3') AND bits >= 128
    ) THEN
        RAISE EXCEPTION 'Secret Store storage requires an encrypted TLS 1.2+ session';
    END IF;
    IF current_database() <> 'kaori_secret_store' OR pg_is_in_recovery()
        OR current_user <> 'kaori_secret_store' OR session_user <> current_user THEN
        RAISE EXCEPTION 'Expected the dedicated primary database and authenticated runtime identity';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolcanlogin
          AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname <> current_user
          AND pg_has_role(current_user, oid, 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'Unexpected privileged storage runtime identity';
    END IF;
    IF has_database_privilege(current_user, 'kaori', 'CONNECT')
        OR has_database_privilege(current_user, current_database(), 'CREATE')
        OR has_database_privilege(current_user, current_database(), 'TEMPORARY')
        OR has_schema_privilege(current_user, 'public', 'CREATE') THEN
        RAISE EXCEPTION 'Unexpected storage runtime database privileges';
    END IF;
END
$verify$;
COMMIT;
\echo PASS: dedicated encrypted storage session; client trust and provider compatibility require separate evidence
