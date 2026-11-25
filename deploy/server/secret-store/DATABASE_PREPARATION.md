# Dedicated PostgreSQL database and role preparation (#5202)

This is a separate DBA-custody step, not a deploy.sh activation. It reuses
the approved bundled PostgreSQL server and fixed logical identities
`kaori_secret_store_owner` (NOLOGIN owner) and `kaori_secret_store` (runtime).
No app database grants, passwords, host files, or provider state are changed.

## First-run only

Before execution, independently confirm the disposable target, PostgreSQL
primary identity, application DB isolation, backup/recovery owner, and
absence of existing dedicated storage and roles. Use a trusted DBA session
on the maintenance database `postgres`, not the app runtime connection.
Execute the reviewed script from that session using the native psql client:

```text
psql --no-psqlrc --dbname=postgres --set=kaori_secret_store_prepare=true --file=deploy/server/secret-store/prepare-storage-database.sql
```

Use independently provisioned authentication; never place passwords in the
command line or shell history. The opt-in is not target authorization.
The script refuses existing identities, wrong database, replica, missing
canonical application identities and PUBLIC CONNECT to the application DB.
It creates the owner and runtime identities as NOLOGIN; the new database
initially disallows connections and only enables them after restricted
database ACL verification. It does not set a password or start OpenBao.

The DBA must separately confirm SCRAM authentication, verified PostgreSQL
TLS and the required pg_hba.conf restrictions, then set a unique runtime
password interactively using native psql `\password kaori_secret_store`
with SCRAM password encryption and explicitly enable LOGIN for that role.
Keep the password only in the service-scoped DSN with verify-full and
the approved CA; never use the app, migrator, or DBA credential. The owner
remains NOLOGIN. Only then run the independently reviewed fresh schema
provisioning procedure. No service startup until schema and TLS admission.

## Failure and recovery

CREATE DATABASE is not transactional with role creation. On any partial
failure the script intentionally refuses a rerun: inspect the actual state
under DBA custody; the new runtime is NOLOGIN and a database created before
ACL admission remains connection-disabled. Do not drop or recreate state
automatically. Existing-state storage must use the separate read-only
verification procedure after its source is admitted. No reset or repair
authorization is implied by this document.

A successful disposable CI test proves database/role SQL behavior only,
not actual host isolation, pg_hba.conf, TLS, credentials, provider
initialization, recovery or operational readiness.
