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

The approved **three-role** design uses the PostgreSQL image's first-volume
superuser `postgres`, a non-superuser schema owner `kaori_migrator`, and
the permanently restricted app login `kaori_runtime`. Only the runtime
credential belongs in the root, ignored `.env`. Both privileged credentials
are held as Compose secrets from the WSL host **outside** the repository and
all bind-mounted application workspaces.

`Reopen in Container` creates all existing services, runs an idempotent
one-shot principal/ownership bootstrap, and does **not** run Alembic, grant
application-table writes or create an application administrator. Existing
`Database Setup Required` remains visible on the empty schema; only the
operator's explicit VS Code task performs migration. The DevContainer
flow is separate from production DBA-owned database authority.

## 0. One-time private development configuration

1. On WSL, checkout the reviewed issue branch until PR #1428 is admitted
   into `kaori/review/staging-uat`. Back up any existing local DB if it
   contains data. An existing **two-role** PostgreSQL volume must not be
   silently converted or reinitialized by this fresh-only design.
2. Store the two privileged secrets **outside** the repository:
   `~/.config/kaori/devcontainer-db/postgres_admin_password` and
   `~/.config/kaori/devcontainer-db/migrator_password`. The first is
   consumed only by the PostgreSQL image and one-shot bootstrap. The
   second is consumed by the one-shot bootstrap and is typed explicitly
   at each DevContainer migration task. Never commit them or place them
   in the bind-mounted workspace or any shared `env_file`.
3. On the WSL host, create them only when absent (no password echo):

```bash
python3 - <<'PY'
from getpass import getpass
from pathlib import Path
import os

directory = Path.home() / '.config/kaori/devcontainer-db'
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(directory, 0o700)
for filename in ('postgres_admin_password', 'migrator_password'):
    destination = directory / filename
    if destination.exists():
        print(f'EXISTS: {destination} — not replacing an established secret')
        continue
    secret = getpass(f'New {filename} (min 16 characters): ')
    if len(secret) < 16:
        raise SystemExit('ABORT: password too short; rerun secret provisioning')
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(secret)
    print(f'CREATED: {destination}')
PY
```

4. Copy root `.env.example` to ignored `.env`, set
   `KAORI_DEV_DB_SECRETS_DIR` to your **absolute WSL host path** (not
   `~` and not a path inside this repo), and set
   `DATABASE_URL=postgresql://kaori_runtime:<url-encoded-runtime-secret>@db:5432/kaori`.
   Use a distinct runtime secret; this password is used by the one-shot
   role creation and by all runtime services. Replace private
   `ADMIN_*`, `SECRET_KEY` and `INTEGRATION_CREDENTIAL_KEY` placeholders.
   Run `git check-ignore -q .env` on the host.
   **Remove** legacy `POSTGRES_USER`, `POSTGRES_DB`,
   `POSTGRES_PASSWORD`, `KAORI_DEV_RUNTIME_DATABASE_URL`, and
   `KAORI_DB_MIGRATION_URL` from root `.env`; none is an application
   credential. PostgreSQL's DevContainer overlay sets
   `POSTGRES_USER=postgres`, `POSTGRES_DB=kaori` and
   `POSTGRES_PASSWORD_FILE` separately.
5. `docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml
   config --quiet` must pass. Do not print full rendered Compose config
   because it can include runtime secrets. **Never** apply these local
   provisioning instructions to external/production PostgreSQL.

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
  grep -q '^KAORI_DEV_DB_SECRETS_DIR=/' .env ||
    fail "absolute WSL host secrets directory missing"
  ! grep -q '^POSTGRES_PASSWORD=' .env ||
    fail "legacy postgres bootstrap password must not be in app .env"
  ! grep -q '^POSTGRES_USER=' .env ||
    fail "legacy PostgreSQL owner must not be in app .env"
  ! grep -q '^POSTGRES_DB=' .env ||
    fail "database service initialization is now separately owned"
  grep -q '^DATABASE_URL=postgresql://kaori_runtime:' .env ||
    fail "canonical DATABASE_URL must use restricted runtime"
  ! grep -q '^KAORI_DEV_RUNTIME_DATABASE_URL=' .env ||
    fail "remove deprecated duplicate runtime URL"
  ! grep -q '^KAORI_DB_MIGRATION_URL=' .env ||
    fail "migration secret must not persist in app .env"
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
Fresh database creation uses DevContainer-only `postgres` configuration and the
outside-workspace Docker secrets; the app `.env` holds only runtime authority.

## 2a. Ordinary fresh DevContainer opening — no manual Compose commands

With the private configuration above, run **VS Code: Dev Containers →
Reopen in Container**. The established `.devcontainer/devcontainer.json`
automatically starts PostgreSQL, Redis, workspace, all ten workers, Beat,
and an idempotent `db-role-bootstrap` one-shot service.

The first empty PostgreSQL cluster creates `postgres` (bootstrap
superuser) and database `kaori`. The one-shot service reads the external
Docker secrets to create `kaori_migrator` (non-superuser and owner of
database/public schema) and the restricted `kaori_runtime` with minimal
`CONNECT`/`USAGE`. It does not create KAORI application tables.
On subsequent reopens it only validates identities and actual logins;
it refuses wrong passwords, elevated roles, ownership mismatch and
unexpected existing schema instead of silently changing data.

Workers and Beat are created but wait behind existing
`WAIT_FOR_SCHEMA=true` and `WAIT_FOR_RUNTIME_GRANTS=true` until the
schema and Capsule ledger ACLs pass. Do not manually start each worker.

Optional read-only evidence from the WSL host:

```bash
kaori_dc() { docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml "$@"; }
kaori_dc ps db redis workspace db-role-bootstrap
kaori_dc logs --tail=50 db-role-bootstrap
kaori_dc exec -T db psql -X -At -U postgres -d kaori \
  -c "SELECT current_database(),
             to_regclass('public.alembic_version') IS NULL,
             to_regclass('public.users') IS NULL,
             EXISTS (SELECT 1 FROM pg_roles WHERE rolname='kaori_migrator'),
             EXISTS (SELECT 1 FROM pg_roles WHERE rolname='kaori_runtime')"
# Before schema initialization: kaori|t|t|t|t
```

Run F5 `KAORI: Flask Debug` and open `http://localhost:5000/auth/login`.
Expected: **HTTP 503 Database Setup Required / Initialization Required**.
This is the already approved read-only operator page, not a web
installer accepting DBA credentials.

## 3. Explicit operator bootstrap — one VS Code task

For a new empty schema, choose **Terminal → Run Task →
KAORI: Initialize Fresh Database**. The existing first-run page's
Copy Command invokes the same
`python -m scripts.devcontainer.initialize_database --bootstrap-admin`.

The task prompts **interactively** for the `kaori_migrator` password.
Obtain it from the trusted external secrets source; do not enter it in
`.env`, VS Code task definitions, shell history or chat. The runner:

1. Confirms development scope, restricted canonical `DATABASE_URL`,
   the actual migrator login and its non-superuser schema DDL rights.
2. Supplies an ephemeral `KAORI_DB_MIGRATION_URL` only to
   `scripts/init_db.sh` for `flask --app run:app db upgrade` and RBAC
   seed, without ever giving it to Flask Debug, workers or Beat.
3. Executes the existing transactional
   `scripts/devcontainer/provision_postgres_runtime_role.sql` as
   `kaori_migrator`, refreshing normal DML/sequence grants while
   enforcing Capsule ledger SELECT/INSERT-only effective privileges.
4. Creates the first **KAORI application administrator** with
   `flask --app run:app bootstrap-admin` using the ordinary
   `kaori_runtime` connection after runtime grants exist.
5. Runs the actual runtime ORM/Capsule ledger guard; workers and Beat
   then unblock when they detect current Alembic head and valid grants.

Expected successful completion contains:

```text
PASS: explicit DevContainer PostgreSQL migration identity admitted
Database migration and RBAC initialization completed.
PASS: migration, runtime ACLs and Capsule ledger guard admitted.
```

Refresh the login page after completion. Normal subsequent DevContainer
opens do not run migrations, recreate the first admin or rotate passwords.

For schema upgrades, choose **KAORI: Database Upgrade**; it prompts
for the migrator password and performs migration plus grant refresh.
Do not run bare `flask db upgrade` under `kaori_runtime`.

## 4. Negative tests and recovery

- Attempting Alembic with runtime credentials must fail DDL authority.
- `kaori_runtime` must not be `SUPERUSER`, `CREATEDB`, `CREATEROLE`,
  schema/ledger owner or a member of `kaori_migrator`; ledger UPDATE,
  DELETE and TRUNCATE must be denied, and immutable triggers enabled.
- An interrupted migration is **not** permission to reset data:
  preserve database and consult the #1405 data-preserving runbook.
- If `db-role-bootstrap` fails, inspect its sanitized logs and check
  for a misplaced `POSTGRES_PASSWORD` in root `.env`, incorrect
  outside-repo secret files, mismatched runtime credentials, unexpected
  ownership, or existing two-role schema. Never fall back to owner
  `DATABASE_URL` or blindly drop a volume.
- Running `Reopen in Container` with a previously initialized volume
  must only validate preexisting principals and preserve all data.
- All provider-mutating tenant/Capsule operations remain governed and
  separately UAT-reviewed. Passing SQL migration does not constitute
  tenant/provider mutation admission.

## 5. Read-only postflight and UAT evidence

From the DevContainer terminal after migrations:

```bash
python - <<'PY'
from run import app
from app.extensions.db import db
from app.kubernetes.tenant.capsule_handoff_start_writer import (
    _require_postgres_ledger_write_once_guards,
)
with app.app_context():
    assert db.engine.url.username == 'kaori_runtime'
    try:
        _require_postgres_ledger_write_once_guards(db.session)
        print('PASS: Flask runtime identity and immutable Capsule ledger admitted')
    finally:
        db.session.rollback()
PY
```

Record actual Alembic heads, the PostgreSQL owner/runtime role flags,
effective ACLs and four write-once ledger triggers, worker/Beat
admission, browser initial 503 and normal login after bootstrap.
Keep Redis queues and any existing workload data intact on reopen.
For a deliberately retained Redis volume during scoped developer reset,
check `kaori_dc exec -T redis redis-cli -n 1 DBSIZE` and queue lengths
before worker/Beat admission. Do not flush or replay old broker jobs against
a new database without separate operator authorization.

The scoped destructive reset above is **not** part of normal first use.
The operator reported a fully empty local installation; no additional
volume deletion is warranted for that UAT.

## 6. Production boundary

Bundled production is governed by #621/#1439; DBA/external PostgreSQL
by #622/#1440 and the DBA-SQL handoff issue #1469. Production **never**
takes the DevContainer `postgres` superuser secrets, auto-creates
remote roles, or executes development tasks. DBA supplies restricted
runtime authority and either a separate migration executor or a
reviewed SQL package applied within DBA-controlled sessions. See
`docs/operations/dba-executed-postgresql-migrations.md` in PR #1470
for the draft operational boundary; it is not yet an executable
admitted SQL package. No staging/main promotion or production DB
mutation is authorized by this local runbook.
