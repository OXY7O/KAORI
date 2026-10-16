-- Read-only PostgreSQL cutover inventory for reviewed bundled UAT (#1439).
-- Execute inside the EXISTING kaori database as its authorized administrator.
-- No CREATE/ALTER/REVOKE/GRANT, data write, or ownership change occurs.
SELECT current_database() AS database_name, current_user AS inspected_by,
       pg_is_in_recovery() AS recovery;
SELECT datname, pg_get_userbyid(datdba) AS database_owner
  FROM pg_database WHERE datname = current_database();
SELECT nspname, pg_get_userbyid(nspowner) AS schema_owner
  FROM pg_namespace WHERE nspname = 'public';
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,
       rolcanlogin FROM pg_roles
 WHERE rolname IN ('postgres', 'kaori', 'kaori_migrator', 'kaori_runtime');
SELECT c.relkind, c.relname, pg_get_userbyid(c.relowner) AS owner
  FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
    AND c.relkind IN ('r','p','v','m','S','f')
 ORDER BY c.relkind, c.relname;
SELECT p.proname, pg_get_function_identity_arguments(p.oid) AS signature,
       pg_get_userbyid(p.proowner) AS owner
  FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
 ORDER BY p.proname, signature;
SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner) AS owner,
       ext.extname AS extension_owner
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  LEFT JOIN pg_depend dep ON dep.classid = 'pg_class'::regclass AND dep.objid = c.oid
                          AND dep.deptype = 'e'
  LEFT JOIN pg_extension ext ON ext.oid = dep.refobjid
 WHERE n.nspname = 'public' AND ext.oid IS NOT NULL;
SELECT current_setting('fsync') AS fsync,
       current_setting('synchronous_commit') AS synchronous_commit,
       current_setting('session_replication_role') AS replication_role;
SELECT r.rolname,
       has_schema_privilege(r.oid, 'public', 'CREATE') AS runtime_schema_create,
       has_database_privilege(r.oid, current_database(), 'TEMPORARY') AS runtime_temp,
       has_database_privilege(r.oid, current_database(), 'CREATE') AS runtime_db_create
  FROM pg_roles r WHERE r.rolname = 'kaori_runtime';
