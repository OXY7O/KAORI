# KAORI production PostgreSQL — governed migration authority and DBA SQL handoff

**Authorities:** #619 → #621 / #622, bounded workstreams #1439 / #1440 and DBA SQL-package child #1467.
**Status:** architecture and operator contract only. The existing
`deploy/server` production adapter currently starts bundled PostgreSQL and
Redis and executes its migration service with the application environment.
**External production adapters, privileged secret isolation and DBA-approved
offline SQL packages are NOT yet implemented/admitted.**

## Two database deployment boundaries

| Dimension | KAORI-bundled PostgreSQL | DBA/provider-managed PostgreSQL |
| --- | --- | --- |
| Database/role provisioner | server bootstrap operation | DBA/provider, not KAORI |
| Superuser/server settings | trusted operator only | DBA only |
| Schema DDL | non-superuser `kaori_migrator` with sufficient object ownership | DBA-authorized migration identity, or DBA-executed reviewed SQL |
| Day-to-day login | `kaori_runtime` in `DATABASE_URL` | separate restricted login (DBA can choose name) |
| Backup/storage/HA | governed local deployment owner | provider/DBA owns lifecycle |
| Redis | current bundled implementation | parent #622 currently supports bundled-both or external-both; mixed mode requires separate approval |

Merely obtaining DBA host/database/username/password authorizes **runtime
connectivity**, not DDL, CREATE ROLE, CREATEDB, SUPERUSER or database restore.
Never use runtime `DATABASE_URL` to run `flask db upgrade`.

## Migration execution policy

**Mode A — controlled migrator:** a separate, protected migration process
uses a DBA-authorized DDL principal, runs the existing Flask-Migrate/Alembic
revision(s), refreshes runtime grants and returns evidence. DDL credentials
must not be included in `/etc/kaori/secrets.env` if that file is passed to
web/workers/Beat. A dedicated secret-delivery mechanism must be admitted
before production automation uses this mode.

**Mode B — DBA-executed SQL:** the DBA retains privileged passwords and runs
a reviewed, immutable **DBA migration package** using their PostgreSQL
administration tool. KAORI does not receive the secret or execute remote DDL.
The package must identify:
- validated **current and target Alembic revision(s)** and exact release SHA;
- ordered PostgreSQL schema changes, data migrations and grants (including
  immutable Capsule ledger triggers, negative privileges and ownership);
- preflight assertions, backup/restore owner, lock/downtime risks,
  transaction boundaries and recovery procedure;
- approved SQL content SHA-256, peer review, DBA execution timestamps,
  SQL completion/error logs (redacted), and DB postcondition queries;
- controlled `alembic_version` advancement only when migration effects
  are actually applied and verified, not blind `flask db stamp`;
- subsequent read-only KAORI runtime admission for schema head,
  effective least privilege, triggers and application readiness.

**Important limitation:** KAORI `migrations/env.py` defines Alembic
`run_migrations_offline()`, but current history includes online-only
migration paths: `20260716_repair_kubernetes_discovery_columns.py`
inspects live schema; `20260817_lifecycle_policy_seed.py` queries rows
before conditional inserts; other migrations perform data-dependent changes
and vendor-specific Capsule trigger DDL. Running
`flask --app run:app db upgrade --sql` is **NOT** an admitted general-purpose
DBA package generator. Each target revision range needs compatibility review,
a verified PostgreSQL SQL artifact and evidence. If not supportable, require
DBA-side approved migration runner or a separately reviewed SQL equivalent.

## Required release/admission sequence

1. Capture current DB revision, provider endpoint identity and trusted
   backup/restore authority (no credentials in committed evidence).
2. Approve migration release SHA, current→target revision and impact/rollback.
3. Have DBA provision appropriate runtime and migrator grants, or execute
   the reviewed SQL change package under provider change control.
4. Record result and verify `alembic_version` plus expected DDL, DML,
   indexes/functions/triggers, and runtime `rolsuper=rolcreatedb=
   rolcreaterole=rolbypassrls=false`.
5. Verify immutable ledger requires SELECT/INSERT only, never UPDATE,
   DELETE/TRUNCATE, and cannot be bypassed through ownership/membership.
6. Only then start/admit normal web and all worker/Beat processes and
   perform staging/UAT with review and human acceptance.

When the database is reachable but schema is absent, the existing
`Database Setup Required` page remains read-only; it is never a route to
send DBA passwords to KAORI or invoke SQL through a browser.

The production SQL generator/admission implementation is tracked separately in
#1467 (child of #1439); do not treat this written contract as a runnable SQL artifact.

This document describes the **target**, not a claim of external-mode
availability or production UAT PASS. Implementation authority and gates
remain tracked in #1439 and #1440.
