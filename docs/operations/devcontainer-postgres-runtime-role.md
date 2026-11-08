# DevContainer PostgreSQL role separation — local, data-preserving procedure

**Scope:** KAORI `kaori-dev` Compose project only. Issue #1405, blocked
Capsule G1 restart #1228/#1229. **No new database, no data move, no DROP,
TRUNCATE, role-owner change, or provider mutation.** The database remains
`kaori`; its existing owner/admin role (reported as `kaori` in local
evidence) stays available for migrations and recovery.

The new `kaori_runtime` role is a non-elevated application login.
Flask, all development Celery workers and Beat use **the same runtime DB
URL** after opt-in; migrations/RBAC bootstrap use a temporary owner
connection. The owner `kaori` must not serve routine application requests.
Existing Capsule PostgreSQL START triggers and the audit handback trigger
remain installed and authoritative.

## Observed diagnosis

The DevContainer application connection returned:
`current_user=kaori`, elevated=true, ledger owner=true,
ledger owner-member=true, and UPDATE/DELETE/TRUNCATE=true.
`fsync=on`, `synchronous_commit=on`, `session_replication_role=origin`
already pass their individual checks. The backend correctly denies Capsule
restart until role/ledger immutability is independently proven.

## Preconditions / non-destructive backup

1. Confirm **development-only** `kaori-dev` is the target, not staging or
   production. Confirm source and current migration head. Pause Flask jobs,
   scheduler and Celery mutation until the cutover; do not stop or delete
   PostgreSQL data volumes.
2. Take a verified backup of the existing database **before** any role DDL.
   From a trusted terminal with the existing database owner credentials
   (the prompts do not write a password into shell history):

   ```bash
   umask 077
   pg_dump -h db -U kaori -W -d kaori -Fc -f /secure/local-path/kaori-before-runtime-role.dump
   pg_restore --list /secure/local-path/kaori-before-runtime-role.dump >/dev/null
   ```

   Use a real writable **private location outside the repository and
   source mounts**. The dump contains application data and must not be
   committed. The backup-list check is not a substitute for an isolated
   restore test. Do not use `docker compose down --volumes`.
3. Confirm the Capsule ledger migrations are installed with the existing
   migration-owner identity (and that no unreviewed database migrations
   are pending). If behind, apply the **approved** migrations through
   existing `flask --app run:app db upgrade` using the owner connection,
   before granting the runtime role. Do not migrate as `kaori_runtime`.

## Step 1 — Provision a single restricted DB role

Use an interactive terminal with `psql`, connected to the *existing*
DevContainer PostgreSQL service. In the actual environment the privileged
owner may be `kaori` (observed) rather than the template's `postgres`;
substitute the **verified owner account** if different.

```bash
PGAPPNAME=kaori-devcontainer-role-provision \
psql -h db -U kaori -W -d kaori -X -v ON_ERROR_STOP=1 \
  -v kaori_devcontainer_confirm=1 \
  -f scripts/devcontainer/provision_postgres_runtime_role.sql
```

This *transactional* SQL refuses non-`kaori` databases, missing current
Capsule ledger/audit schema, non-admin connections, elevated or
owner-member target roles, and unexpected effective ledger privileges.
It grants normal existing-table DML and sequence usage without CREATE,
and overrides Capsule ledger grants to **SELECT and INSERT only**.
It does **not** grant future table privileges by default: **no blanket ALTER DEFAULT PRIVILEGES** is permitted for this runtime role. Rerun the
role-grant step after an approved migration adds tables or sequences,
**before** worker restart. That prevents default broad UPDATE/DELETE
on newly created immutable evidence tables.

The new role starts `NOLOGIN`. Assign its credential using an
interactive PostgreSQL prompt, never shell command arguments, committed
files or a SQL literal:

```bash
psql -h db -U kaori -W -d kaori -X
```

Inside that `psql` session:

```text
\password kaori_runtime
ALTER ROLE kaori_runtime LOGIN;
\q
```

Choose an independent strong development password. If the role already
exists and is in use, coordinate credential rotation instead of blindly
resetting it; rerunning grants alone does not rotate or disable login.

## Step 2 — Verify restricted privileges before switching applications

Connect **as the new role** with `psql -h db -U kaori_runtime -W -d kaori -X`.
The following is read-only:

```sql
BEGIN READ ONLY;
SELECT current_database(), current_user,
       current_setting('fsync') AS fsync,
       current_setting('synchronous_commit') AS synchronous_commit,
       current_setting('session_replication_role') AS replication_role;
SELECT r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication,
       r.rolbypassrls, pg_get_userbyid(c.relowner) = current_user AS owns_ledger,
       pg_has_role(r.oid, c.relowner, 'MEMBER') AS member_of_owner,
       has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
       has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(current_user, c.oid, 'DELETE') AS can_delete,
       has_table_privilege(current_user, c.oid, 'TRUNCATE') AS can_truncate
FROM pg_class c JOIN pg_roles r ON r.rolname = current_user
WHERE c.oid = 'public.capsule_handoff_ledger_events'::regclass;
ROLLBACK;
```

Expected: all five elevated flags false; owns/member=false;
SELECT/INSERT=true; UPDATE/DELETE/TRUNCATE=false; WAL settings
`on/on/origin`. Also verify the four PostgreSQL Capsule ledger
triggers are enabled, including `tr_capsule_ledger_deny_truncate`,
and the G5 handback audit protections before any later G5 action.
A missing/misconfigured guard **must** keep Capsule Release denied.

## Step 3 — Opt-in runtime cutover, all service connections

Add **only to your ignored private root `.env`**:

```dotenv
KAORI_DEV_RUNTIME_DATABASE_URL=postgresql://kaori_runtime:<URL-encoded-runtime-password>@db:5432/kaori
```

URL-encode special password characters. Never commit this value.
The Compose override applies the same URL to workspace, all named Celery
workers and Beat. An unset variable falls back to the existing owner
connection **for backward compatibility only**; that path is deliberately
**NOT Capsule-ledger-admitted**. Do not mistake successful UI startup for
ledger authority.

Recreate the application/worker containers using the existing
`compose.yml` + `.devcontainer/compose.devcontainer.yml` DevContainer
lifecycle (or VS Code **Rebuild/Reopen in Container**). This may interrupt
the active VS Code terminal; save work before recreating `workspace`.
**Do not recreate/reset `db`, and never use `down --volumes`.**
For host-side inspection use:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
```

With the runtime container running, verify using its effective
`DATABASE_URL`, not the owner `psql` session. Check the runtime DB role
for Flask and representative Celery workers and Beat. Verify ordinary
CRUD, audit append, inventory worker queries and sequence-backed INSERT,
then the existing Capsule guarded PostgreSQL role/trigger checks.
**A role switch does not certify provider handoff or UAT.**

## Step 4 — Future migrations and database rollback

For later owner-only migrations, supply `KAORI_DB_MIGRATION_URL`
**temporarily to the existing `scripts/init_db.sh` invocation**.
Do **not** persist this privileged connection in `.env` (the latter
is supplied to all development workers). The script refuses an ownerless
migration after the runtime URL is configured. After Alembic migration,
reapply the explicit runtime grants as the owner, review protected tables,
and reconnect the runtime role. Workers already retain their existing
`WAIT_FOR_SCHEMA=true` gate.

If application behavior fails **before any Capsule START**, safely stop
application processes and inspect permission errors. Restore previous
`KAORI_DEV_RUNTIME_DATABASE_URL` value or unset it only for reversible
DevContainer application troubleshooting; doing so restores the legacy
owner runtime and **must leave Capsule handoff/restart disabled**.
The role and table grants need not be dropped to roll back the
application URL. Do not delete immutable ledger evidence, reset the
database, or auto-retry any uncertain provider PATCH. Preserve logs and
use normal recovery if START/attempt history exists.

## Security boundary / limitations

This dev-only procedure separates *normal DB sessions*, but the current
root `.env` is mounted into development containers and also holds
`POSTGRES_PASSWORD` used by the Compose DB service. A compromised
development process with read access to that file could potentially
discover the owner credential and connect as owner. **Do not claim
hostile-process tamper resistance** from the runtime role alone. Isolate
owner credentials using the governed secrets boundary before any
staging/production rollout. Those environments have separate deployment
configuration and are **out of scope** of this change.

No migration, provisioning SQL or runtime cutover was executed through
the GitHub-only implementation path. Operator-run DevContainer
verification, existing quality gates and human acceptance are still
needed. CI/CD, staging/main promotion and Kubernetes mutation remain HOLD.
