# DevContainer PostgreSQL fresh bootstrap — explicitly destructive local UAT

**Scope:** issue #1427 (follow-up to #1405). **Only** the developer's
`kaori-dev` Compose PostgreSQL named volume may be destroyed. This is an
explicit operator-authorized **fresh database** procedure, not the
data-preserving remediation in
[the #1405 runbook](devcontainer-postgres-runtime-role.md).
It deletes all local PostgreSQL `kaori` tables, users held in that cluster,
Tenant/`kaori-demo` records, approvals and audit/Capsule evidence.
Do not apply on a shared environment, staging, production, or any other
Compose project. Previous backups remain outside the repo; verify their
availability before proceeding. This procedure cannot prove restore safety.

The design uses exactly one `DATABASE_URL` for the application: the
`kaori_runtime` login. The PostgreSQL/bootstrap owner is configured with
`POSTGRES_USER=kaori`, `POSTGRES_DB=kaori` and a distinct
`POSTGRES_PASSWORD`. Owner-only Alembic/RBAC/admin bootstrap supplies
`KAORI_DB_MIGRATION_URL` **to one child process** (never `.env`, workers or
Beat). Credentials must never be printed in logs or committed to Git.

## 0. Preconditions — read before destructive action

1. Checkout the reviewed code implementing #1427, including
   `.devcontainer/compose.devcontainer.yml`, `.env.example`, and
   `scripts/init_db.sh`. Do not reset against mismatched source.
2. Confirm the private root `.env` has one
   `DATABASE_URL=postgresql://kaori_runtime:<url-encoded-secret>@db:5432/kaori`;
   remove obsolete `KAORI_DEV_RUNTIME_DATABASE_URL`; retain
   `POSTGRES_DB=kaori`, `POSTGRES_USER=kaori`, and its existing
   `POSTGRES_PASSWORD`. Use different owner/runtime credentials.
   `KAORI_DB_MIGRATION_URL` must **not** be saved in any `.env` file.
   `git check-ignore -q .env` must pass.
3. Confirm the prior archived backup is readable, if it may be needed.
   In this development UAT a previous `pg_restore --list` archive check
   exists, but it is not an actual restore test.
4. Stop Flask Debug and any locally running jobs. Pause external cron
   or developer processes connecting to this database. Ensure Docker Desktop
   and the intended WSL host are in the correct environment.
5. Keep Redis, the instance/workspace volumes, other Docker projects, and
   Kubernetes/external providers **untouched**. No provider PATCH,
   Kubernetes reconciliation mutation, or staging/production changes.

## 1. Check current state before resetting (WSL host)

The reset **must not** start until the expected issue branch and the
private environment contract have been confirmed. A blank result from a
shell with `set -e` is **not** a PASS; the original operator attempt
returned no deletion output and therefore did not establish fresh state.

From the KAORI repository root:

```bash
git branch --show-current
git status --short
kaori_dc() {
  docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml "$@"
}
kaori_dc ps db redis
kaori_dc exec -T db sh -c \
  'psql -X -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
   -c "SELECT current_database(),
              to_regclass('\''public.alembic_version'\'') IS NULL,
              to_regclass('\''public.users'\'') IS NULL,
              EXISTS (SELECT 1 FROM pg_roles WHERE rolname='\''kaori_runtime'\'')"'
```

An empty schema has the form `kaori|t|t|f`. If it is already fresh,
**skip deletion entirely** and continue to optional step 2a. A present
schema (`kaori|f|f|t`) means old state remains. Do not destroy anything
based solely on `pg_isready`, which proves connectivity, not emptiness.

## 2. Guarded PostgreSQL-only deletion (WSL host)

This block runs **only** when the operator explicitly intends to
discard the disposable local DB and the preceding query shows old state.
It validates the project, branch, private runtime URL, service and
**exact** named PostgreSQL volume, including its Docker Compose project
label, before stopping/removing the database. Each failure reports a
specific `ABORT` reason; Redis and all other volumes remain unchanged.

```bash
(
  set -euo pipefail

  fail() { printf 'ABORT: %s\n' "$*" >&2; exit 1; }

  [[ "$(git branch --show-current)" == \
    "kaori/issue-1427-devcontainer-fresh-bootstrap" ]] ||
    fail "checkout the reviewed #1427 implementation branch first"

  [[ -f .env ]] && git check-ignore -q .env ||
    fail "private ignored root .env is missing"
  grep -q '^POSTGRES_DB=kaori$' .env ||
    fail "POSTGRES_DB must be kaori"
  grep -q '^POSTGRES_USER=kaori$' .env ||
    fail "POSTGRES_USER must be kaori"
  grep -q '^POSTGRES_PASSWORD=.' .env ||
    fail "POSTGRES_PASSWORD is missing"
  grep -q '^DATABASE_URL=postgresql://kaori_runtime:' .env ||
    fail "canonical DATABASE_URL must use the restricted role"
  ! grep -q '^KAORI_DEV_RUNTIME_DATABASE_URL=' .env ||
    fail "remove deprecated duplicate runtime URL"
  ! grep -q '^KAORI_DB_MIGRATION_URL=' .env ||
    fail "migration owner URL must not persist in .env"
  kaori_dc config --quiet || fail "DevContainer Compose configuration invalid"

  PG_CONTAINER="$(kaori_dc ps -q db)"
  [[ -n "$PG_CONTAINER" ]] || fail "db container is not running"
  PG_PROJECT="$(docker inspect -f \
    '{{index .Config.Labels "com.docker.compose.project"}}' "$PG_CONTAINER")"
  PG_SERVICE="$(docker inspect -f \
    '{{index .Config.Labels "com.docker.compose.service"}}' "$PG_CONTAINER")"
  PG_VOLUME="$(docker inspect -f \
    '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' \
    "$PG_CONTAINER")"
  printf 'Target: project=%s service=%s volume=%s\n' \
    "$PG_PROJECT" "$PG_SERVICE" "$PG_VOLUME"

  [[ "$PG_PROJECT" == "kaori-dev" ]] ||
    fail "unexpected Compose project"
  [[ "$PG_SERVICE" == "db" ]] ||
    fail "unexpected PostgreSQL service"
  [[ "$PG_VOLUME" == "kaori-dev_kaori_postgres_data" ]] ||
    fail "unexpected PostgreSQL volume"
  OWNER_LABEL="$(docker volume inspect "$PG_VOLUME" \
    --format '{{index .Labels "com.docker.compose.project"}}')"
  [[ "$OWNER_LABEL" == "kaori-dev" ]] ||
    fail "volume Compose ownership label is '$OWNER_LABEL', expected kaori-dev"

  printf 'PASS: exact DevContainer PostgreSQL data volume admitted for reset\n'

  kaori_dc stop \
    beat inventory-worker registry-security-worker maintenance-worker \
    runtime-worker validation-worker analytics-worker reports-worker \
    forecasting-worker resolver-execution-worker resolver-maintenance-worker
  kaori_dc stop db
  kaori_dc rm -f db
  docker volume rm "$PG_VOLUME"

  printf 'PASS: previous DevContainer PostgreSQL volume removed\n'
  kaori_dc up -d --no-deps db
  kaori_dc ps db redis
)
```

Wait until PostgreSQL reports `healthy`. Rerun the read-only
`to_regclass` check from step 1 and require `kaori|t|t|f` before
continuing. If the script prints `ABORT`, diagnose that reason; do
not substitute `down -v`, `down --volumes`, Docker prune, or remove
an unexpected volume. The current DevContainer `workspace` process
may stay running, but keep **Flask Debug, workers and Beat stopped**.
Fresh database creation uses private `POSTGRES_DB/USER/PASSWORD`.

## 2a. Ordinary fresh DevContainer opening — no manual Compose commands

When a developer uses **Dev Containers: Reopen in Container**, the
existing `.devcontainer/devcontainer.json` `runServices` starts **all**
services: PostgreSQL, Redis, workspace, ten workers and Beat. A new
`db-role-bootstrap` one-shot Compose service is a startup dependency of
workspace/workers/Beat. It creates `kaori_runtime` with a distinct
password derived only from the private canonical `DATABASE_URL` and
minimal database CONNECT/public schema USAGE on an **empty bundled
PostgreSQL cluster**. It does **not** create schema, grant application
table writes, run migration or create an administrator. On subsequent
reopens it checks the existing role and login; it does not rotate
passwords, mutate prior records, or drop a role. If it fails, inspect its
logs before proceeding. Do not fall back to the PostgreSQL owner.

Workers/Beat automatically start with `WAIT_FOR_SCHEMA=true` and
`WAIT_FOR_RUNTIME_GRANTS=true`; until schema reaches current Alembic
head **and** the restricted ledger ACLs have been provisioned they
**wait without consuming jobs**. This preliminary worker gate is not a
substitute for the Capsule START transaction's independent full guard.
There is no need to manually stop/start 10 worker containers for normal
first-run operation.

Read-only verification on WSL host (if diagnosing first-run):

```bash
kaori_dc ps db redis workspace db-role-bootstrap
kaori_dc logs --tail=60 db-role-bootstrap
kaori_dc exec -T db psql -X -At -U kaori -d kaori \
  -c "SELECT current_database(),
             to_regclass('public.alembic_version') IS NULL,
             to_regclass('public.users') IS NULL,
             EXISTS (SELECT 1 FROM pg_roles WHERE rolname='kaori_runtime')"
# Expected before initialization: kaori|t|t|t
```

The same read-only check prior to Compose first-run would have returned
`kaori|t|t|f`. The role's presence is expected **after** automatic
one-shot login provisioning. The initial database and restricted role
exist, but the KAORI application tables intentionally do not.

Open `KAORI: Flask Debug` (F5) and browse to
`http://localhost:5000/auth/login`. Expected **HTTP 503 —
Database Setup Required / Initialization Required** with the missing
authentication tables. This is KAORI's existing read-only readiness
page, not an installer that accepts DBA credentials in the browser.
Take UI evidence if a first-run checkpoint is required.

## 3. One-time VS Code Initialize Fresh Database task

Only on the first empty KAORI schema, choose
**Terminal → Run Task → `KAORI: Initialize Fresh Database`**.
The task runs `python -m scripts.devcontainer.initialize_database
--bootstrap-admin` and deliberately delegates to existing
`scripts/init_db.sh` and
`scripts/devcontainer/provision_postgres_runtime_role.sql`.

The workflow:

1. Verifies the selected environment is the **local bundled** `kaori-dev`
   database and the configured runtime role is not the PostgreSQL owner.
2. Constructs an **ephemeral** `KAORI_DB_MIGRATION_URL` from
   `POSTGRES_USER/PASSWORD/DB` for a child migration process, without
   writing it to `.env` or passing it to workers.
3. Runs owner-only Alembic upgrades, canonical RBAC seeding and the
   explicit first administrator bootstrap. Developer-supplied
   `ADMIN_*` and `INTEGRATION_CREDENTIAL_KEY` must be set in the
   private development environment before using this task.
4. Runs the existing transactionally guarded DevContainer role
   provisioning/grant SQL using the PostgreSQL owner, preserving
   `kaori_runtime` LOGIN/password and restricting immutable Capsule
   ledger to SELECT/INSERT only.
5. Reuses the existing Flask ORM Capsule PostgreSQL write-once
   guard. If any stage fails, STOP and review logs; do not bypass grants,
   turn off triggers, or start provider actions.

Expected final output includes:

```text
PASS: explicit DevContainer PostgreSQL migration identity admitted
Database migration and RBAC initialization completed.
PASS: KAORI migrated; restricted runtime grants and Capsule ledger guard admitted.
```

Refresh `/auth/login` after success to view KAORI sign-in.
**The task is not run on ordinary container reopen**, so existing data,
migrations, and credentials are not re-created repeatedly.

After intentional future Alembic migrations, use the existing
**KAORI: Database Upgrade** VS Code task. It runs owner migration
then refreshes restricted runtime table privileges. **KAORI: Seed RBAC**
and **KAORI: Bootstrap Admin** also use the controlled owner path;
bare `flask db upgrade` as `kaori_runtime` must not be used.

## 4. Manual recovery only

For an advanced operator diagnosing a failed role or migration,
the **existing** provisioning SQL and runbook under
[DevContainer PostgreSQL runtime role](devcontainer-postgres-runtime-role.md)
remain the approved recovery authorities. Do not manually create the
runtime role, rotate owner credentials, or delete volumes during normal
fresh-container opening. The one-shot Compose service cannot provision
arbitrary DBA-owned production endpoints; these are governed by
the production database lifecycle issues #621/#622.

## 5. Verify actual ORM, PostgreSQL guard and worker admission

First in a **fresh VS Code terminal** (close stale integrated terminals):

```bash
python - <<'PY'
from run import app
from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _require_postgres_ledger_write_once_guards,
)

with app.app_context():
    assert db.engine.url.username == "kaori_runtime"
    try:
        _require_postgres_ledger_write_once_guards(db.session)
        print("PASS: Flask ORM uses restricted PostgreSQL ledger-guarded role")
    finally:
        db.session.rollback()
PY
```

Verify migration version matches `flask --app run:app db heads`;
confirm the role lacks elevated flags, ledger ownership and all
immutable UPDATE/DELETE/TRUNCATE privileges as in the #1405 runbook.

**Redis job-safety checkpoint:** Redis is intentionally retained.
Before resuming workers, check the existing development Redis broker
for stale pre-reset queue payloads (names derive from existing KAORI
Celery topology) and unacknowledged messages:

```bash
# WSL host — read-only, does not reset Redis
for queue in inventory registry-security maintenance integration-runtime \
  integration-validation analytics-batch reports forecasting \
  resolver-execution resolver-maintenance
do
  printf '%s: ' "$queue"
  kaori_dc exec -T redis redis-cli -n 1 LLEN "$queue"
done
kaori_dc exec -T redis redis-cli -n 1 HLEN unacked
kaori_dc exec -T redis redis-cli -n 1 DBSIZE
```

If any queue or `unacked` count is nonzero, keep workers and Beat
stopped and investigate those old jobs. `DBSIZE` alone may count
binding metadata, not pending messages. Never blindly flush Redis or
replay pre-reset jobs against the new database. Clear/purge only with
separate explicit operator authorization.

When queue state is safe, from WSL host:

```bash
kaori_dc up -d --no-deps \
  inventory-worker registry-security-worker maintenance-worker \
  runtime-worker validation-worker analytics-worker reports-worker \
  forecasting-worker resolver-execution-worker resolver-maintenance-worker
```

Confirm all ten use the canonical `DATABASE_URL` as `kaori_runtime`,
and `celery --app celery_worker:celery_app inspect ping` and
`inspect active_queues` return expected consumers. Start `beat`
only when these pass and the scheduler is safe to resume.

Launch Flask Debug using VS Code F5 and test local login, dashboard
reads, ordinary safe DB INSERT/UPDATE with audit append, and
`python scripts/verify_reports_worker_runtime.py`. Provider-mutating
tasks and provider handoff remain HOLD.

## 6. Scope and acceptance

The wiped development Tenant/plan/audit records **cannot** be used
as evidence for an expired Capsule G1 restart. Create a legitimate
new development test fixture/plan through the governed UI and normal
approval flow before a controlled G1 UAT. **Do not** fabricate history,
reset guards, bypass preflight or infer readiness from an empty ledger.

Record the exact source commit, Docker volume ID/name, migration head,
provisioning output, restricted ORM/ACL/trigger results, Celery/Flask
functional results, and explicit human acceptance in GitHub issue #1427.
No CI/CD, Full Admission, staging/main promotion or release is implied.
