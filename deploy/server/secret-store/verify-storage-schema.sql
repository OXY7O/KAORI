-- #5202: read-only existing-state check for the dedicated OpenBao 2.7 database.
-- Run as authorized DBA after provisioning, before restart or recovery admission.
-- Does not read KV records, initialize the provider, repair ACLs or change storage.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
DO $verify$
DECLARE
    storage_oid oid;
    actual_columns text[];
BEGIN
    IF current_database() <> 'kaori_secret_store' OR pg_is_in_recovery() THEN
        RAISE EXCEPTION 'Refusing Secret Store verification outside its primary dedicated database';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user AND rolsuper) THEN
        RAISE EXCEPTION 'Expected independently authorized PostgreSQL administrator';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kaori_secret_store_owner' AND NOT rolcanlogin
          AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kaori_secret_store' AND rolcanlogin
          AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) OR EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname <> 'kaori_secret_store'
          AND pg_has_role('kaori_secret_store', oid, 'MEMBER')
    ) THEN
        RAISE EXCEPTION 'Storage identities missing or elevated';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database WHERE datname = current_database()
          AND pg_get_userbyid(datdba) = 'kaori_secret_store_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_namespace WHERE nspname = 'public'
          AND pg_get_userbyid(nspowner) = 'kaori_secret_store_owner'
    ) THEN
        RAISE EXCEPTION 'Unexpected database or schema ownership';
    END IF;
    SELECT c.oid INTO storage_oid
      FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
        AND c.relname = 'openbao_kv_store' AND c.relkind = 'r'
        AND c.relpersistence = 'p' AND NOT c.relrowsecurity AND NOT c.relforcerowsecurity
        AND pg_get_userbyid(c.relowner) = 'kaori_secret_store_owner';
    IF storage_oid IS NULL THEN
        RAISE EXCEPTION 'Expected owned persistent storage table not found';
    END IF;
    SELECT array_agg(a.attname || ':' || format_type(a.atttypid, a.atttypmod) ||
        ':' || a.attnotnull::text || ':' || COALESCE(co.collname, '-')
        ORDER BY a.attnum) INTO actual_columns
      FROM pg_attribute a LEFT JOIN pg_collation co ON co.oid = a.attcollation
      WHERE a.attrelid = storage_oid AND a.attnum > 0 AND NOT a.attisdropped;
    IF actual_columns IS DISTINCT FROM ARRAY[
        'parent_path:text:true:C', 'path:text:true:C', 'key:text:true:C', 'value:bytea:false:-'
    ]::text[] THEN
        RAISE EXCEPTION 'Storage column contract mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conrelid = storage_oid AND contype = 'p'
          AND convalidated AND conkey = ARRAY[2, 3]::smallint[]
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_am am ON am.oid = c.relam
        WHERE i.indrelid = storage_oid AND c.relname = 'openbao_kv_store_idx'
          AND i.indisvalid AND i.indisready AND NOT i.indisunique
          AND i.indnatts = 1 AND i.indkey::text = '1'
          AND i.indpred IS NULL AND i.indexprs IS NULL AND am.amname = 'btree'
    ) THEN
        RAISE EXCEPTION 'Storage primary key or parent-path index mismatch';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgrelid = storage_oid AND NOT tgisinternal
    ) OR EXISTS (
        SELECT 1 FROM pg_rewrite WHERE ev_class = storage_oid
    ) THEN
        RAISE EXCEPTION 'Unexpected storage triggers or rules';
    END IF;
    IF NOT has_database_privilege('kaori_secret_store', current_database(), 'CONNECT')
        OR NOT has_schema_privilege('kaori_secret_store', 'public', 'USAGE')
        OR has_database_privilege('kaori_secret_store', 'kaori', 'CONNECT')
        OR has_database_privilege('kaori_runtime', current_database(), 'CONNECT')
        OR has_database_privilege('kaori_migrator', current_database(), 'CONNECT')
        OR has_database_privilege('kaori_secret_store', current_database(), 'CREATE')
        OR has_database_privilege('kaori_secret_store', current_database(), 'TEMPORARY')
        OR has_schema_privilege('kaori_secret_store', 'public', 'CREATE')
        OR EXISTS (
            SELECT 1 FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) AS p(privilege)
            WHERE NOT has_table_privilege('kaori_secret_store', storage_oid, p.privilege)
               OR has_table_privilege('kaori_secret_store', storage_oid, p.privilege || ' WITH GRANT OPTION')
        ) OR EXISTS (
            SELECT 1 FROM unnest(ARRAY['TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) AS p(privilege)
            WHERE has_table_privilege('kaori_secret_store', storage_oid, p.privilege)
        ) OR EXISTS (
            SELECT 1 FROM unnest(ARRAY['kaori_runtime','kaori_migrator']) AS r(role_name)
            CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) AS p(privilege)
            WHERE has_table_privilege(r.role_name, storage_oid, p.privilege)
        ) THEN
        RAISE EXCEPTION 'Storage effective ACL contract mismatch';
    END IF;
END
$verify$;
COMMIT;
\echo PASS: dedicated Secret Store schema and effective ACL; TLS and runtime admission still required
