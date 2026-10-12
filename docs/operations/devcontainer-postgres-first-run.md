# KAORI DevContainer PostgreSQL — first run with three segregated roles

**Authority:** #1427 (DevContainer only, under #1405 immutable Capsule ledger guard).
**Scope:** developer-owned disposable `kaori-dev` PostgreSQL. This is NOT a DBA/external
database provisioning procedure and must never be applied to production.

## Lifecycle: opening a zero-volume DevContainer

1. Start VS Code in WSL, open this project, and choose **Reopen in Container**.
   `.devcontainer/devcontainer.json` still includes all 14 `runServices`:
   workspace, PostgreSQL, Redis, ten Celery workers and one Beat. No manual
   `docker compose up` is needed.
2. The **host-side** `initializeCommand` runs
   `.devcontainer/prepare-postgres-env.py` *before* the services start.
   If root `.env` is absent, it copies the committed `.env.example`
   automatically. It then writes the generated runtime
   `DATABASE_URL`, application encryption secrets (if missing) and first
   administrator password (if placeholder) into that private `.env`.
   It creates or aligns the application `.env` and writes
   `~/.config/kaori/devcontainer/postgres-bootstrap.env` and
   `postgres-migrate.env`, mode 0600, outside the bind-mounted repository.
   The first file holds the PostgreSQL bootstrap and local runtime provisioning
   secrets. The second holds only the migration role password. Do not copy
   either into the repository or expose them in chat/logs.
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
5. Use **Copy Command** on that page, then run it from a **WSL HOST terminal**
   at the repository root (not inside the DevContainer terminal):

   ```bash
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
   ```

   The one-off Compose service receives ONLY `postgres-migrate.env` (never
   `postgres-bootstrap.env`) and normal `.env`. It runs:
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

~/.config/kaori/devcontainer/postgres-bootstrap.env
  POSTGRES_PASSWORD=<generated-postgres-superuser-password>
  KAORI_RUNTIME_PASSWORD=<generated-runtime-role-password>

~/.config/kaori/devcontainer/postgres-migrate.env
  KAORI_MIGRATOR_PASSWORD=<generated-migrator-role-password>
```

The values in angle brackets above are **descriptions**, not real
credentials or a file to paste unchanged. The actual passwords are
generated with cryptographic randomness by the WSL host initializer,
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

From the WSL host:

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

## Existing volume, migration upgrades, and recovery

- Reopening with a persistent volume **does not** regenerate passwords,
  reinitialize roles, delete data or run Alembic automatically.
- When a newer source introduces a migration, explicitly execute from the
  WSL host:

  ```bash
  docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml \
    run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
  ```

  This migrates/refreshes grants/seeds RBAC but never creates another first
  administrator. Workers/Beat wait for current migration heads and role
  admission throughout.
- Existing data migration requires reviewed backup and recovery. The
  historical data-preserving #1405 cutover runbook is preserved for old
  `kaori`-owner clusters; do **not** apply the new first-volume-only
  provisioning script retroactively to an existing cluster.
- If root `.env` or either secret file becomes inconsistent with a
  persistent volume, the initializer **aborts**. Recover the original
  matching credentials; never regenerate them against existing data.
- Host preparation treats **only Docker's explicit "no such volume"**
  result as a fresh database. Failure to contact Docker, malformed
  inspection output, or a named volume without the exact
  `kaori-dev` Compose project and `kaori_postgres_data` volume labels
  is an **ABORT**, not permission to regenerate credentials.
- Existing host-side PostgreSQL secret files must be owned by the
  developer and mode `0600`; the enclosing external directory must
  be developer-owned mode `0700`. Symlinked files or a secret directory
  resolving inside the repository are rejected. The initializer
  protects the app `.env` with mode `0600` without rotating secrets.
- PostgreSQL's first-volume role init reads bootstrap passwords through
  `psql` environment-variable support rather than command-line
  `-v password=...` arguments, to avoid exposing secrets via process
  argument inspection. This remains a **trusted local Docker host**
  boundary, not a production secrets-manager equivalent.
- The host initializer assumes VS Code is running in a WSL environment with
  `python3`, Docker/Compose and a normal `$HOME`. Other host platforms
  require an explicit adapter review; don't silently move secrets into the
  workspace.

**Review boundary:** this implementation does not operate a provider-owned
database, does not expose a DDL wizard through HTTP, and does not enable
production schema auto-migration. Formal CI/CD and admission remain HOLD until
developer verification and explicit acceptance.
