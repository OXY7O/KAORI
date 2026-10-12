# KAORI DevContainer PostgreSQL — first run with three segregated roles

**Authority:** #1427 (DevContainer only, under #1405 immutable Capsule ledger guard).
**Scope:** developer-owned disposable `kaori-dev` PostgreSQL. This is NOT a DBA/external
database provisioning procedure and must never be applied to production.

## Supported VS Code Windows + Docker Desktop launch

Open the checkout in **VS Code for Windows**, including a Windows/OneDrive
working tree. Choose **Dev Containers: Rebuild and Reopen in Container**
with Docker Desktop running Linux containers. Remote-WSL, WSL terminal,
and a Windows-installed Python interpreter are **not required**.

`.devcontainer/devcontainer.json` invokes Docker directly as a host
`initializeCommand`: a transient `python:3.12-alpine` container bind
mounts the checkout and mounts two private Docker named volumes. This
container generates/validates the ignored application `.env` and role
credentials, then exits. Docker subsequently starts the existing
services. If VS Code fails with `Exit code 1`, use the **first error**
in the Dev Containers log: the final CLI stack trace is insufficient.

The volumes `kaori-dev-pg-admin-secrets` and
`kaori-dev-pg-migrator-secrets` are outside the working tree and
never mounted to workspace, Flask, Celery workers or Beat.
Do not remove volumes simply because no containers are running.
The secret volumes use mode 0700 directories/0600 files readable by
the pinned PostgreSQL 16 container UID, with separate mounts by role.

## Lifecycle: opening a zero-volume DevContainer

1. Start **VS Code Windows** from the existing checkout and choose **Rebuild and Reopen in Container**.
   `.devcontainer/devcontainer.json` still includes all 14 `runServices`:
   workspace, PostgreSQL, Redis, ten Celery workers and one Beat. No manual
   `docker compose up` is needed.
2. The cross-platform Docker `initializeCommand` runs
   `python /workspace/.devcontainer/prepare-postgres-env.py` **inside a disposable Python container** before services start.
   If root `.env` is absent, it copies the committed `.env.example`
   automatically. It then writes the generated runtime
   `DATABASE_URL`, application encryption secrets (if missing) and first
   administrator password (if placeholder) into that private `.env`.
   It creates/validates `kaori-dev-pg-admin-secrets` (two private
   files: `postgres_password`, `runtime_password`) and
   `kaori-dev-pg-migrator-secrets` (one private file: `password`).
   These are Docker volumes, not files in the Windows workspace. No
   postgres or migrator password is copied into application `.env`.
3. The PostgreSQL 16 official image initializes an **empty volume only** with
   `POSTGRES_USER=postgres` and database `kaori`. Its
   `/docker-entrypoint-initdb.d/01-kaori-roles.sh` creates `kaori_migrator`
   (non-superuser schema owner) and `kaori_runtime` (restricted login).
   It grants only CONNECT/USAGE to runtime before schema creation; Alembic,
   RBAC and administrator creation are **not** run automatically.
4. The workspace starts; start **KAORI: Flask Debug** (F5). The runtime
   `DATABASE_URL` connects as `kaori_runtime`, so
   `http://localhost:5000/auth/login` returns **HTTP 503,
   Database Setup Required — Initialization Required**. This existing page
   stays read-only. All workers and Beat containers exist, but schema/ledger
   admission holds them before they consume/schedule jobs.
5. Use **Copy Command** and run it in **Windows PowerShell on the host**
   from the repository root, not inside the DevContainer terminal:

   ```bash
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
   ```

   The one-off Compose service mounts ONLY the migrator Docker secret
   volume (never the postgres/runtime bootstrap volume) and normal
   application `.env`. It runs:
   - `flask --app run:app db upgrade` with temporary **kaori_migrator** connection;
   - `grant_postgres_runtime.sql` as migrator after migrations, with negative
     Capsule ledger privileges and schema CREATE restrictions;
   - `flask --app run:app bootstrap-admin` under `kaori_runtime` after grants;
   - immutable Capsule ledger admission check using runtime.
   No one-off migrator URL remains in application environment or on disk.
6. Refresh the login page, then authenticate using the configured
   `ADMIN_USERNAME` and private `ADMIN_PASSWORD` in `.env`. Do not paste
   the password in issue/PR logs.

## Effective ENV values — what changes after first Reopen

This is the **DevContainer-only** file layout; there is no need to manually
create an administrative PostgreSQL role or copy privileged passwords into
the application `.env`:

```text
<KAORI repository>/.env
  APP_ENV=development
  POSTGRES_DB=kaori
  POSTGRES_USER=postgres              # infrastructure selector, NOT Flask login
  POSTGRES_PORT=5432
  DATABASE_URL=postgresql://kaori_runtime:<generated-password>@db:5432/kaori
  SECRET_KEY=<generated-if-placeholder>
  INTEGRATION_CREDENTIAL_KEY=<generated-if-empty>
  ADMIN_USERNAME=admin
  ADMIN_EMAIL=admin@example.com       # customize before first admin bootstrap
  ADMIN_PASSWORD=<generated-if-placeholder>
  REDIS_URL=redis://redis:6379/0
  CELERY_BROKER_URL=redis://redis:6379/1
  CELERY_RESULT_BACKEND=redis://redis:6379/3

Docker volume kaori-dev-pg-admin-secrets
  postgres_password    # credential for postgres (bootstrap only)
  runtime_password     # credential for kaori_runtime (runtime URL generated from this)

Docker volume kaori-dev-pg-migrator-secrets
  password             # credential for kaori_migrator, non-superuser DDL
```

The values in angle brackets above are **descriptions**, not real
credentials or a file to paste unchanged. The actual passwords are
generated with cryptographic randomness by the Docker-based initializer,
not committed to GitHub, logged, or sent in chat. A new private
`.env` is created automatically from `.env.example` if missing.
If you want to customize `ADMIN_EMAIL`/`ADMIN_USERNAME` or any other
non-secret settings, you may copy the template **before** first opening.
Do not change the generated runtime URL while retaining an existing DB
volume. Do not define `POSTGRES_PASSWORD`, `KAORI_RUNTIME_PASSWORD`,
`KAORI_MIGRATOR_PASSWORD`, `PGPASSWORD` or
`KAORI_DB_MIGRATION_URL` inside the application `.env`.

`POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PORT` are present in
the root app file only to provide Compose infrastructure defaults.
`POSTGRES_USER=postgres` **does not** mean Flask uses `postgres`;
only the canonical `DATABASE_URL` selects the DB identity used by
Flask, workers and Beat.

**Who gets the secrets?** The `db` service receives the bootstrap
and migrator initdb credentials. The explicit one-off `db-bootstrap`
receives the migrator file and runtime app `.env`. Ordinary
`workspace`, web, workers and Beat receive neither privileged
PostgreSQL file. The host files must be `0600` and external
directory `0700`. Production and external DBA deployments use the
existing governed split `/etc/kaori/{app,secrets,deploy}.env`
instead, and **must not** reuse these local credentials.

## PostgreSQL identities

| Role | Provisioner | Allowed use | Prohibited use |
| --- | --- | --- | --- |
| `postgres` | PostgreSQL official empty-cluster init | local bootstrap and local role provisioning | Flask, workers, Beat, daily app DML |
| `kaori_migrator` | one-time initdb script | own KAORI schema, Alembic DDL and grants refresh | ordinary app runtime, SUPERUSER, CREATEDB, CREATEROLE |
| `kaori_runtime` | one-time initdb script | ORM/application DML after grants; Capsule ledger SELECT/INSERT | schema CREATE, owner membership, ledger UPDATE/DELETE/TRUNCATE |

`DATABASE_URL` is the **only** app/worker database connection. There is no
`KAORI_DEV_RUNTIME_DATABASE_URL` fallback. `POSTGRES_PASSWORD` is **not**
present in the root application `.env` and is never sent to the worker
containers. In this disposable development mode, a trusted Docker host
administrator can still inspect secrets supplied to its own database
container; this is not a substitute for a production secrets manager.

## Safe read-only UAT checkpoints

From the Windows host:

```bash
kaori_dc() { docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml "$@"; }
kaori_dc ps
kaori_dc exec -T db psql -U postgres -d kaori -X -At -c "
SELECT current_database(),
       to_regclass('public.alembic_version') IS NULL,
       to_regclass('public.users') IS NULL,
       (SELECT count(*) FROM pg_roles WHERE rolname IN ('kaori_migrator', 'kaori_runtime'));"
```

**Before bootstrap** expected: `kaori|t|t|2`. The application should
render HTTP 503 **Initialization Required** (not **Database Unavailable**).

**After bootstrap**, verify role separation and ledger privileges:

```bash
kaori_dc exec -T db psql -U postgres -d kaori -X -At -c "
SELECT r.rolname, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
       r.rolbypassrls
FROM pg_roles r WHERE r.rolname IN ('kaori_migrator','kaori_runtime')
ORDER BY r.rolname;
SELECT has_table_privilege('kaori_runtime',
                          'public.capsule_handoff_ledger_events','INSERT'),
       has_table_privilege('kaori_runtime',
                          'public.capsule_handoff_ledger_events','UPDATE'),
       has_table_privilege('kaori_runtime',
                          'public.capsule_handoff_ledger_events','DELETE'),
       has_table_privilege('kaori_runtime',
                          'public.capsule_handoff_ledger_events','TRUNCATE');"
```

Expected ledger flags: `t|f|f|f`. Additionally, `kaori_runtime` has
`SELECT` only (no `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`) on
`public.alembic_version`: the application must not falsify migration state.
Run the existing #1405 runtime guard
and actual UI CRUD/audit/Capsule UAT before declaring PASS. Capture sanitized
Docker logs, schema version and role/trigger evidence.

## Existing database and first-run recovery

- Existing database data and roles are **never** silently reset. A missing
  Docker secret file, mismatched runtime URL, or incomplete credential
  pair is a failing preflight; preserve volumes and application `.env`.
- `docker volume ls` can reveal named volumes even when `docker ps`
  displays no running containers. Never use `down --volumes` for normal
  troubleshooting. The two credential volumes are external Docker
  volumes and intentionally survive Compose shutdown.
- For migration upgrades (after an accepted backup), run from Windows
  PowerShell at the repository root:

  ```powershell
  docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
  ```

  This updates schema/grants without re-creating the first KAORI admin.
- The old two-role `kaori`-owned PostgreSQL volume must go through a
  separate, data-preserving review/cutover. The Docker initializer
  refuses missing secret state or an existing unmatched runtime URL.
  Do not overwrite existing credentials to make a connection work.

**Windows note:** `.env` remains an ignored local application runtime
configuration in the source checkout; on NTFS/OneDrive its host privacy
is governed by Windows ACL and sync policy, not Unix `chmod` alone.
No elevated PostgreSQL secret is stored there. For production or
external DBA databases, do not use these local volumes, roles or
commands; follow #1439/#1440/#1469 instead.

**Admission:** This branch is for local function testing first;
CI/CD, Full Admission, staging human UAT and main promotion remain
HOLD until explicitly requested and verified.
