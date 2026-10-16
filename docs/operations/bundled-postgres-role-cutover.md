# Bundled PostgreSQL role cutover — server/Staging UAT (#1439)

Status: implementation candidate, NOT a live database execution record.
This runbook applies to the existing `deploy/server` Compose adapter and its
persistent `kaori-vps-postgres-data` volume. PostgreSQL is not replaced.
External DBA-managed PostgreSQL is tracked separately by #1440.

## Fast path: staging database has no application schema

This is the preferred path for the currently reported empty Staging/UAT
database. **No volume deletion, `down -v`, ownership-reassignment SQL or
manual per-table grants.** The same database and bundled container are kept.

1. Verify that the database is genuinely unused/uninitialized. "Zero data
   rows" is not the same as "no schema." The deployment checks existing user
   database objects, and the one-shot bootstrap checks all user schemas,
   public relations, functions, extensions, other sessions, role presence and
   ownership. If any check disagrees, it fails closed.
2. Configure three server-only connection identities:
   - `postgres-admin.env`: preserve the *existing* original
     `POSTGRES_PASSWORD` (do not rotate it as part of this change).
   - `postgres-migrate.env`: `KAORI_DB_MIGRATION_URL` using
     `kaori_migrator` and a distinct strong password.
   - `secrets.env`: `DATABASE_URL` using `kaori_runtime` and its own
     distinct strong password. Remove `POSTGRES_PASSWORD` from shared
     secrets, leaving all other application keys unchanged.
   Use URL-percent-encoding for reserved password characters and 0600 mode.
   Do not print credentials, paste them in the PR or commit real environment
   files. The `bootstrap-host.sh` prepares examples without overwriting
   existing files; fill the new values through the authorized host channel.
3. In `/etc/kaori/deploy.env`, set
   `KAORI_BUNDLED_FRESH_BOOTSTRAP=true` **only for the first governed
   Staging/UAT deployment**. Keep `POSTGRES_USER` equal to the currently
   initialized database administrator; do not rename that user.
4. The existing `deploy/server/deploy.sh` automatically executes:
   PostgreSQL/Redis health → strict empty-database and credentials preflight
   → one-shot `db-provision` (creates both restricted roles and transfers
   ownership of the *empty* database and `public` schema in a transaction)
   → `migrate` (Alembic as `kaori_migrator`)
   → transactionally refreshed runtime privileges
   → one-shot `db-bootstrap-admin` as `kaori_runtime`
   → `db-verify` (migration heads, immutable ledger triggers/ACLs and admin)
   → normal web/workers/Beat → release evidence.
5. Once the first release and its UAT evidence have passed, set
   `KAORI_BUNDLED_FRESH_BOOTSTRAP=false` for subsequent deployments.
   Existing populated databases take the normal **backup → migrate → verify**
   path and are NEVER re-provisioned automatically.

If there are existing migration tables or any user objects (even with zero
records), use the separately reviewed existing-state path below instead.
Do not use `docker volume rm`, `DROP DATABASE` or `flask db stamp`
to force the fast path to run.

## Observed staging host — 2026-10-16 (existing schema, not first-run)

Read-only inventory from the authorized staging operator:

- Bundled container `kaori-production-postgres-1` healthy; database `kaori`.
- Legacy database administrator `kaori` is SUPERUSER with CREATEDB and CREATEROLE.
- Database owned by `kaori`; `public` schema owned by `pg_database_owner`.
- Existing objects: 99 regular tables, 88 sequences and 587 indexes, all
  owned by `kaori`; no application-owned functions reported.
- Alembic baseline `20261004_registry_analytics`. This branch also includes newer
  migrations through `20261013_limit_exposure`, and some migrations explicitly
  state source-only / do not execute without their own admission. **Do NOT
  auto-upgrade this staging schema as a side effect of role cutover.** The
  existing deployment script still invokes `flask db upgrade`; separate
  admission is required before activation.
- PostgreSQL estimated about 34,704 rows in
  ten nonempty tables (statistical estimate, not an exact count).
- Neither `kaori_migrator` nor `kaori_runtime` role exists.
- Admin/migrator/runtime host secret files are mode 0600, owner kaori-deploy;
  their contents have not been validated remotely.

**DO NOT use the empty-database fast path on this host.** The database already
contains schema and application data. An opt-in cutover requires a backed-up
existing-schema maintenance run. Keep `KAORI_BUNDLED_FRESH_BOOTSTRAP=false`.

### Bounded existing-schema path

**Schema-pin requirement:** for the role-only cutover, the candidate's exact
Alembic head set must equal the already-applied staging `alembic_version`
set. If different (currently the case: staging `20261004_registry_analytics`
versus newer files through `20261013_limit_exposure`), the deployment
fails **before stopping application services, dumping data or issuing DDL**.
New feature-schema migrations require independent admission first.

After the candidate passes source/DB/restore test gates and maintenance is
approved, set `KAORI_BUNDLED_SCHEMA_CUTOVER=true` for ONE governed deployment.
Keep `KAORI_BUNDLED_FRESH_BOOTSTRAP=false` and existing `POSTGRES_USER=kaori`.
The deploy adapter will stop existing application writers, make the custom
database dump, independent schema dump and global-role recovery dump,
verify checksums and the custom dump manifest, and then invoke the protected
`db-provision` one-shot service with `cutover` argument.

That operation refuses unexpected roles, schema kinds, extensions, functions,
object owners, concurrent connections and database administrators. It creates
the separate restricted principals, transfers the audited existing public
application tables/sequences and their dependent indexes to the migrator,
updates database/schema owners and revokes public authority in a transaction.
It does not drop, truncate, recreate or copy application rows. The normal
migration/grant/immutable-admission pipeline then runs as before.

After accepted UAT, set `KAORI_BUNDLED_SCHEMA_CUTOVER=false`. A second
cutover attempt refuses previously migrated database ownership. Keep
`*.roles.sql` backup artifacts locked down: they include PostgreSQL
authentication verifiers and must never be posted in public logs/issues.
Database dump existence/checksum alone does NOT constitute a verified
rollback; rehearse restore in an isolated instance before host activation.

## Access boundaries

| Principal | Credential delivery | Intended access |
| --- | --- | --- |
| Current `POSTGRES_USER` administrator (possibly legacy `kaori`) | `/etc/kaori/postgres-admin.env`, mode 0600, `postgres` only | Server bootstrap, operator-approved provisioning, backup/restore |
| `kaori_migrator` | `/etc/kaori/postgres-migrate.env`, mode 0600, `migrate` only | Owner of database, public schema, migrations, schema objects and post-migration DML grants |
| `kaori_runtime` | `DATABASE_URL` in `/etc/kaori/secrets.env`, mode 0600 | Flask, all Celery workers and Beat; never owner, never DDL |

Neither `POSTGRES_PASSWORD` nor `KAORI_DB_MIGRATION_URL` may be
defined in the shared application `app.env` or `secrets.env`.
`POSTGRES_USER` is the PostgreSQL image's original bootstrap role, not an
instruction to rename an existing database account to `postgres`.
The service-scoped files hold protected host secrets; nothing is written to Git,
the release manifest or application/worker containers. The Docker deploy user
remains a trusted host administrator due to Docker daemon access.

## Existing-state path only: preconditions for a database that already has schema

1. The exact source SHA, immutable image digest and accepted UAT change window
   must be recorded. Keep the old release and database available.
2. Stop user writes and all Celery/Beat job producers before ownership changes.
   This is a maintenance cutover, NOT a zero-downtime ACL flip.
3. Make a custom-format `pg_dump` of the existing database and retain the
   protected `.schema.sql` ownership snapshot/checksums from `backup.sh`.
   Separately inventory cluster roles/memberships. The normal custom dump
   uses `--no-owner`: it does NOT back up global roles or their passwords.
4. Prove `pg_restore --list <backup.dump>` succeeds, and perform an isolated
   recovery rehearsal before relying on the archive. Keep the original
   volume untouched.
5. Run the read-only `deploy/server/inventory-postgres.sql` against the
   currently initialized bundled database, not the
   `/docker-entrypoint-initdb.d/` first-volume-only initialization path.
   As the authorized PostgreSQL administrator, inspect the following SQL:

```sql
SELECT current_database();
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
FROM pg_roles WHERE rolname IN ('postgres', 'kaori', 'kaori_migrator', 'kaori_runtime');
SELECT datname, pg_get_userbyid(datdba) AS database_owner
FROM pg_database WHERE datname = 'kaori';
SELECT nspname, pg_get_userbyid(nspowner) AS schema_owner
FROM pg_namespace WHERE nspname = 'public';
SELECT c.relkind, c.relname, pg_get_userbyid(c.relowner) AS owner
FROM pg_class c WHERE c.relnamespace = 'public'::regnamespace
  AND c.relkind IN ('r','p','v','m','S','f') ORDER BY c.relkind, c.relname;
SELECT p.proname, pg_get_userbyid(p.proowner) AS owner
FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace;
SELECT version_num FROM public.alembic_version;
```

If the source database/objects have unexpected owners, extensions,
nonpublic schemas or multiple overlapping application principals: **HOLD**.
Do not run a cluster-wide `REASSIGN OWNED`: it can also affect shared objects
and is not a reviewed per-object ownership migration.

## One-time provisioning / cutover (explicit operator action)

1. Apply the explicitly reviewed `deploy/server/provision-postgres-roles.sql`
   through `psql -X -v ON_ERROR_STOP=1` as the trusted bundled admin, after
   verifying the inventory. It creates missing restricted roles as **NOLOGIN**
   only and refuses existing elevated roles. Set independent strong passwords
   using trusted interactive `psql` `\\password kaori_migrator` and
   `\\password kaori_runtime`, then enable `LOGIN` only after both secret
   files are prepared. Do not grant runtime membership in the owner, or vice
   versa. Never put plaintext passwords into SQL, Git, shell history or logs.
2. Inspect candidate SQL from read-only `deploy/server/plan-postgres-ownership.sql`.
   Under the reviewed maintenance window, transfer ownership of **only the
   audited KAORI database/schema and owned application tables, sequences,
   views and functions** to `kaori_migrator`. Review extension ownership and
   dependent objects independently. Do not rename/drop the legacy superuser
   or use `DROP DATABASE`, `DROP ROLE`, `down -v`, `TRUNCATE` or
   `flask db stamp`. The no-owner cutover is a separate reviewed SQL change
   requiring a tested rollback path, not something the release script infers.
3. As the authorized DB owner/admin, revoke unsafe inherited privileges:
   `REVOKE CREATE, TEMPORARY ON DATABASE kaori FROM PUBLIC;`
   and `REVOKE CREATE ON SCHEMA public FROM PUBLIC;`. Review pre-existing
   role memberships/grants and `PUBLIC` ACLs before revoking anything else.
   Grant `CONNECT` and schema `USAGE` to the runtime role.
4. Create the two protected server-only files from
   `deploy/env/postgres-admin.env.example` and
   `deploy/env/postgres-migrate.env.example`. Preserve the PostgreSQL
   bootstrap password originally used on the existing database. Put
   `KAORI_DB_MIGRATION_URL=postgresql://kaori_migrator:<encoded-password>@postgres:5432/kaori`
   **only** in the migration file. Put the restricted
   `DATABASE_URL=postgresql://kaori_runtime:<encoded-password>@postgres:5432/kaori`
   only in `secrets.env`. Remove the old `POSTGRES_PASSWORD` assignment
   from `secrets.env` after the admin-only file is confirmed. Keep all
   protected files regular, non-symlink, mode 0600 and readable solely
   by the trusted deployment identity.
5. Render the merged Compose configuration with `docker compose config
   --quiet` (never print full Compose configuration with real secrets).
   Test the migrator and runtime connections independently from their
   respective one-shot/service-scoped contexts. The new
   `scripts/server_database_boundary.py migrator` refuses any legacy
   database/object ownership mismatch before Alembic executes.
6. Run the governed deployment with the immutable RC. Its order is:
   PostgreSQL/Redis healthy → pre-migration dump + schema evidence →
   environment validation → migrator owner/ACL preflight → Alembic →
   transactionally refreshed runtime DML privileges → one-shot runtime
   verification → application services → per-service identity/health check.
   If any stage fails, the release is **not** committed.
7. On a new database with no active super administrator, initialize the app
   administrator **separately**, using the runtime-only
   `db-bootstrap-admin` Compose profile after migrations and grants.
   It is intentionally not run automatically during deploy. Repeat the
   governed deployment after that operator-governed app bootstrap.

## Negative admission / acceptance evidence

Capture sanitized output for: owner `DATABASE_URL` rejection; missing
migrator/admin secret; migration URL targeting another DB; missing migration
permissions; unexpected relation/function ownership; runtime role membership
in owner; database/schema CREATE or TEMPORARY privilege; immutable Capsule
ledger UPDATE/DELETE/TRUNCATE rejection; read-only Alembic revision;
four enabled ledger triggers; WAL fsync/synchronous commit; first administrator;
healthy web and every worker/Beat actual DB session. Validate CRUD/audit,
Capsule START append-only, reports, rollback and tested restoration.

A failed grant refresh, unexpected role, incomplete migrations or missing
administrator blocks admission. Do not force a success, stamp a revision, or
remove existing PostgreSQL volumes to get a green pipeline.

## Recovery / deliberate HOLD

Use the tested protected archive, verified role/ownership inventory and
previous immutable image. The governed `restore.sh` imports objects as
`kaori_migrator`, refreshes restrictive grants, validates the restored
runtime, and leaves application processes stopped until a governed
redeploy/rollback. PostgreSQL role/password and external ownership changes
are cluster-level changes; a `pg_dump` alone does not undo them. Do not
claim a safe rollback until the corresponding administrative role/ownership
recovery plan has been rehearsed.

GitHub source changes do not perform or prove a live database cutover. Record
the exact staging SHA, test/run logs, backup/restore evidence and human
acceptance before checking #1439 complete or enabling a UAT release.
