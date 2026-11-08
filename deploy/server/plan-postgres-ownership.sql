-- READ-ONLY ownership migration candidate plan (#1439).
-- Output is NOT an approved executable plan; review extension dependencies,
-- legacy owner, relation ownership and rollback before running any DDL.
SELECT format('ALTER DATABASE %I OWNER TO kaori_migrator;', datname) AS candidate_sql
  FROM pg_database
 WHERE datname = 'kaori' AND pg_get_userbyid(datdba) <> 'kaori_migrator';
SELECT format('ALTER SCHEMA %I OWNER TO kaori_migrator;', nspname) AS candidate_sql
  FROM pg_namespace
 WHERE nspname = 'public' AND pg_get_userbyid(nspowner) <> 'kaori_migrator';
SELECT format(
         'ALTER %s %I.%I OWNER TO kaori_migrator;',
         CASE c.relkind WHEN 'r' THEN 'TABLE' WHEN 'p' THEN 'TABLE'
           WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW'
           WHEN 'm' THEN 'MATERIALIZED VIEW' WHEN 'f' THEN 'FOREIGN TABLE'
         END,
         n.nspname, c.relname
       ) AS candidate_sql, pg_get_userbyid(c.relowner) AS old_owner
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S','v','m','f')
   AND pg_get_userbyid(c.relowner) <> 'kaori_migrator'
 ORDER BY c.relkind, c.relname;
SELECT format(
         'ALTER %s %I.%I(%s) OWNER TO kaori_migrator;',
         CASE p.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END,
         n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)
       ) AS candidate_sql, pg_get_userbyid(p.proowner) AS old_owner
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) <> 'kaori_migrator'
 ORDER BY p.proname;
-- IMPORTANT: extension-owned objects and dependent sequences may require
-- different order or must remain under the extension owner. No auto-execution.
