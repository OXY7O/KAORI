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

## 1. Locate and guard the exact PostgreSQL volume (WSL host)

Run from the KAORI repository root on the WSL host:

```bash
kaori_dc() {
  docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml "$@"
}

PG_CONTAINER="$(kaori_dc ps -q db)"
test -n "$PG_CONTAINER" || { echo "ABORT: kaori-dev db container not found"; exit 1; }

PG_PROJECT="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$PG_CONTAINER")"
PG_SERVICE="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$PG_CONTAINER")"
PG_VOLUME="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$PG_CONTAINER")"

printf 'Project: %s\nService: %s\nPostgreSQL volume: %s\n' "$PG_PROJECT" "$PG_SERVICE" "$PG_VOLUME"
test "$PG_PROJECT" = "kaori-dev" &&
test "$PG_SERVICE" = "db" &&
test "$PG_VOLUME" = "kaori-dev_kaori_postgres_data" ||
  { echo "ABORT: unexpected PostgreSQL container/volume"; exit 1; }

test "$(docker volume inspect "$PG_VOLUME" --format '{{index .Labels "com.docker.compose.project"}}')" = "kaori-dev" ||
  { echo "ABORT: PostgreSQL volume project ownership differs"; exit 1; }
```

If **any** assertion fails, **STOP**; do not guess an alternative volume
name. Do not use `docker compose down -v`, `down --volumes`, or prune.

## 2. Delete only the authorized PostgreSQL data (WSL host)

These commands are destructive and must follow step 1. They keep Redis,
its volume and other Compose-managed data intact.

```bash
kaori_dc stop \
  beat inventory-worker registry-security-worker maintenance-worker \
  runtime-worker validation-worker analytics-worker reports-worker \
  forecasting-worker resolver-execution-worker resolver-maintenance-worker

kaori_dc stop db
kaori_dc rm -f db
docker volume rm "$PG_VOLUME"
kaori_dc up -d --no-deps db
kaori_dc ps db redis
```

Do not start workers or Beat yet. The `workspace` process only sleeps
until Flask Debug is explicitly started. VS Code may reconnect if the
workspace was independently recreated. PostgreSQL must show healthy
before moving on. Fresh cluster initialization consumes the existing
`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` private values.

## 2a. Optional first-run UI checkpoint — schema deliberately absent

KAORI already ships a **read-only** `Database Setup Required` surface
under `http://localhost:5000/auth/login`. To exercise the exact
**Initialization Required** branch **before** Alembic migrations, the
PostgreSQL instance and `kaori` database must exist, the non-owner
`kaori_runtime` login must connect, and the schema tables must be absent.
A missing database or missing login displays **Database Unavailable**,
not the missing-schema state.

After the scoped deletion in step 2, while all Celery workers and Beat
are **stopped**, inspect the freshly initialized schema as the owner:

```bash
psql -h db -U kaori -W -d kaori -X -At \
  -c "SELECT to_regclass('public.alembic_version') IS NULL,
             to_regclass('public.users') IS NULL"
# Expected: t|t
```

**Do not proceed** if either value is false: it is not an empty-schema
first-run environment. There is no need to create a second database.

The existing post-migration provisioning script rightly requires
`audit_events` and the Capsule ledger tables; it **cannot run before
migrations**. For the first-run preview only, pre-create the exact same
non-owner PostgreSQL role *without table grants* using the owner
connection:

```bash
psql -h db -U kaori -W -d kaori -X
```

Inside that owner psql session (no password literals):

```sql
CREATE ROLE kaori_runtime
  NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS INHERIT;
GRANT CONNECT ON DATABASE kaori TO kaori_runtime;
GRANT USAGE ON SCHEMA public TO kaori_runtime;
```

Then use interactive psql meta-command `\password kaori_runtime`
(the runtime secret must match private `DATABASE_URL`), followed by:

```sql
ALTER ROLE kaori_runtime LOGIN;
```

Exit via `\q`. This preview role has **no application table grants**
because the tables do not yet exist. If the role already exists,
revisit the supposed fresh-volume reset rather than silently changing
an existing role.

Check the non-owner session and missing schema:

```bash
psql -h db -U kaori_runtime -W -d kaori -X -At \
  -c "SELECT current_user, to_regclass('public.users') IS NULL"
# Expected: kaori_runtime|t
```

In a fresh VS Code terminal, verify the Flask ORM connects as
`kaori_runtime`, then start `KAORI: Flask Debug` via F5 and browse to
`http://localhost:5000/auth/login`. The expected response is
**HTTP 503 — Database Setup Required / Initialization Required**,
listing missing authentication tables. This is an operator-facing,
read-only installation guidance page, **not** an interactive schema
creation wizard. Stop Flask Debug after taking UI evidence and **before
running migrations**; keep workers and Beat stopped.

When continuing with step 3, owner Alembic creates the actual tables.
Then the established provisioning SQL in step 4 recognizes the
existing `kaori_runtime` role and grants the necessary DML while
enforcing Capsule ledger negative ACL checks. **Do not re-create or
rotate** the role/password if the preview already configured it
correctly.

## 3. Owner-only Alembic + RBAC/admin initialization (DevContainer)

Inside `/workspace/kaori`, run the **existing** `scripts/init_db.sh`
with a transient owner URL assembled from private bootstrap settings.
The URL remains in a child-process environment; this prints neither
password nor connection string, and does not write secrets to `.env`.

```bash
python - <<'PY'
import os
import subprocess
from dotenv import dotenv_values
from sqlalchemy.engine import URL

values = dotenv_values(".env")
assert values.get("POSTGRES_DB") == "kaori"
assert values.get("POSTGRES_USER") == "kaori"
assert values.get("POSTGRES_PASSWORD")
assert values.get("DATABASE_URL", "").startswith("postgresql://kaori_runtime:")

owner_url = URL.create(
    "postgresql",
    username="kaori",
    password=values["POSTGRES_PASSWORD"],
    host="db",
    port=5432,
    database="kaori",
).render_as_string(hide_password=False)

subprocess.run(
    ["sh", "scripts/init_db.sh", "--bootstrap-admin"],
    env={**os.environ, "KAORI_DB_MIGRATION_URL": owner_url},
    check=True,
)
print("PASS: Owner-only migrations and admin/RBAC bootstrap completed")
PY
```

Review reported Alembic migrations through the current `db heads`;
do not run `flask db upgrade` unqualified as `kaori_runtime`.
Verify the resulting schema with read-only owner `psql` if needed.
Bootstrap-admin requires approved local `ADMIN_*` settings and
must not be run against another database.

## 4. Install restricted runtime role using the existing SQL

Run as the trusted owner from the DevContainer terminal:

```bash
PGAPPNAME=kaori-devcontainer-role-provision \
psql -h db -U kaori -W -d kaori -X -v ON_ERROR_STOP=1 \
  -v kaori_devcontainer_confirm=1 \
  -f scripts/devcontainer/provision_postgres_runtime_role.sql
```

After `COMMIT`, **if step 2a was skipped**, open
`psql -h db -U kaori -W -d kaori -X`, run interactive
`\\password kaori_runtime`, then
`ALTER ROLE kaori_runtime LOGIN;` and `\\q`.
Enter the independently generated runtime secret matching
`DATABASE_URL`, without exposing it in chat or Git.
If step 2a already created a working runtime login, **do not reset
the credential**: the existing provisioning script grants permissions
to that role without replacing its password. It grants normal table DML and sequence usage,
but only SELECT/INSERT on `capsule_handoff_ledger_events`, no
UPDATE/DELETE/TRUNCATE, and no `public` schema CREATE. The four
ledger and three handback audit triggers come from Alembic migrations.

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
