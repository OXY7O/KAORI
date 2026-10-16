# Bundled PostgreSQL role cutover — server/Staging UAT (#1439)

Status: implementation candidate, NOT a live database execution record.
This runbook applies to the existing `deploy/server` Compose adapter and its
persistent `kaori-vps-postgres-data` volume. PostgreSQL is not replaced.
External DBA-managed PostgreSQL is tracked separately by #1440.

## Fast path: only for a *proven uninitialized* bundled database

This path is **NOT applicable to the current UAT host**: live read-only
inventory proved an existing `kaori` database with 99 tables, Alembic
`20261004_registry_analytics`, and a legacy `kaori` superuser owner.
Only a separate, genuinely uninitialized installation may use this flow.
**No volume deletion, `down -v`, ownership-reassignment SQL or manual
per-table grants.** Preserve the same database and bundled container.

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

## Existing-schema activation: one governed path, no manual role DDL

**For the observed UAT database (99 tables / Alembic `20261004_registry_analytics`):
DO NOT use the fresh bootstrap.** `KAORI_BUNDLED_FRESH_BOOTSTRAP=false`
must remain false. The operator has only prepared the protected
`postgres-admin.env` / `postgres-migrate.env` files; neither new role exists
yet and no SQL ownership cutover has occurred.

**Important: the source-only** `provision-postgres-roles.sql` **and**
`plan-postgres-ownership.sql` **are review/planning artifacts, not an
additional step to execute before the automatic bundled cutover.** The
`server_database_boundary.py cutover` command deliberately refuses
pre-created role names or non-legacy object owners. Mixing manual role DDL
and the governed in-place path would cause an ambiguous partial cutover.
Do not execute those SQL files or issue manual `CREATE ROLE`, `ALTER OWNER`,
`GRANT` or `REVOKE` on this bundled UAT host.

Follow this exact order, each stage requiring evidence:

1. **Keep the deployed legacy release healthy.** While `v0.3.0-rc.6` is
   active, `/etc/kaori/secrets.env` must retain a working `DATABASE_URL`
   for the existing `kaori` role and `POSTGRES_PASSWORD` for the legacy
   deployment adapter. The operator has verified that legacy database login
   works and restored the URL on disk without restarting containers.
   Keep both `KAORI_BUNDLED_FRESH_BOOTSTRAP=false` and
   `KAORI_BUNDLED_SCHEMA_CUTOVER=false`.
2. **Admit the reviewed feature schema first, separately from role ownership.**
   Existing Alembic `20261004_registry_analytics` and candidate migration
   heads through `20261013_limit_exposure` are NOT equivalent. Under issue
   #1710, first fix admission (#2203), verify all source-only or
   review-required migrations, rehearse the schema upgrade/restore on an
   isolated copy, and release/deploy the approved feature schema under
   the **legacy adapter**. Never run a source-only/DO-NOT-EXECUTE migration
   merely to align version numbers. Preserve immutable release identity.
3. **Prove matching Alembic heads before preparing the role-only release.**
   With an authorized read-only SQL session:
   `SELECT version_num FROM public.alembic_version;` must match the
   *exact* migration heads in the approved role-cutover image. Review
   `inventory-postgres.sql`, role flags, database/schema and per-object
   owner, public ACLs, active sessions, and extension/function inventories.
   Any difference means HOLD; no credential switch.
4. **Rehearse the complete role cutover and recovery in isolated PostgreSQL.**
   A `pg_dump` checksum plus `pg_restore --list` is NOT a recovery test.
   Restore the protected backup and globals into a disposable, access-isolated
   instance, execute the role transfer and privilege checks there, and
   demonstrate recovery to the previous roles/ownership and application
   behavior. Review all expected relation/sequence/index ownership, runtime
   CRUD/immutable ledger denial and Alembic write-only-by-migrator.
5. **Approve one maintenance window and one immutable RC.** Before release,
   prepare the distinct protected `/etc/kaori/postgres-admin.env`
   (`POSTGRES_PASSWORD` of existing `kaori` administrator) and
   `/etc/kaori/postgres-migrate.env` (URL for future `kaori_migrator`)
   plus the future `DATABASE_URL` for `kaori_runtime`, but do not
   publish passwords. Keep the new-role URLs off active legacy services.
   At the approved cutover boundary, atomically update
   `/etc/kaori/secrets.env` to the new `DATABASE_URL` and remove its
   legacy `POSTGRES_PASSWORD`. Preserve original owner, 0600 mode and
   a protected rollback copy. Keep admin/migrator credentials ONLY in their
   service-scoped files; no privileged key in `app.env`.
6. **Use the existing Staging Deploy workflow with exactly one cutover opt-in.**
   Set `KAORI_BUNDLED_SCHEMA_CUTOVER=true` in `/etc/kaori/deploy.env`
   for the **one authorized UAT release only**. The approved
   `deploy/server/deploy.sh` will compare candidate and database Alembic
   heads BEFORE draining writers, stop web/workers/Beat, take full DB +
   schema + global-role protected backups, verify checksums and archive,
   create the two restricted login roles and transfer only approved objects
   transactionally, run Alembic solely as `kaori_migrator`, apply scoped
   runtime privileges, verify Capsule immutable ledger/runtime identity,
   and start/verify all services. A fail-closed outcome is NOT acceptance.
7. **Post-acceptance:** confirm web and every worker/Beat use
   `kaori_runtime`, with no owner/superuser membership, and that the
   migration URL never appears in their container environments; verify
   secure audit/CRUD/report paths and runtime negative privilege tests.
   Change `KAORI_BUNDLED_SCHEMA_CUTOVER=false` after the approved UAT
   evidence is recorded, without restarting only to update this flag.
   Do not promote to `main` without independent acceptance.

Do not run manual `flask db upgrade` with the ordinary runtime URL, edit
`alembic_version` by hand, rotate/drop the legacy `kaori` superuser,
delete volumes, or use `REASSIGN OWNED`. Do not enable role cutover while
PR #2202 remains Draft and restore/schema-head admission has not passed.

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
