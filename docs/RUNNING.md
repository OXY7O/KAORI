# Running KAORI

This document is the canonical entry point for three supported Docker Compose runtime modes:
1. **Local development (Dev Container):** root `.env` + `compose.yml` + `.devcontainer/compose.devcontainer.yml` (`kaori-dev` project, bind-mounted source and VS Code debugging).
2. **Local standalone (no Dev Container):** `example/kaori/.env` + `example/kaori/compose.yml` (`kaori-laptop` project, admitted immutable RC image rather than live local source).
3. **Governed server (UAT/production):** `/etc/kaori/{app,secrets,deploy}.env` + generated `/var/lib/kaori/deploy-state/release.env`, merged `compose.production.yml` + `deploy/server/compose.server.yml` (immutable release and backup/migrate/verify flow).

The files and Docker volumes for these modes are intentionally separate. A root development `.env` must never become the source of production credentials.

## Mode 1 — Local development in VS Code Dev Container

### 1. Prepare the application environment

`.env.example` is the **app-only DevContainer template**. The Docker-host
`initializeCommand` automatically creates private root `.env` if it
does not already exist and replaces the placeholder runtime
`DATABASE_URL` with a generated `kaori_runtime` credential. You may
instead copy it before first open to choose your own
`ADMIN_EMAIL`/`ADMIN_USERNAME` and optional development settings:

```bash
# Optional — skip when the host should generate .env from its template.
cp .env.example .env
```

The app `.env` contains non-secret `POSTGRES_DB=kaori`,
`POSTGRES_USER=postgres` (the **image's bootstrap role**, not a Flask
login), `POSTGRES_PORT=5432`, runtime
`DATABASE_URL=postgresql://kaori_runtime:<generated-password>@db:5432/kaori`,
`SECRET_KEY`, `INTEGRATION_CREDENTIAL_KEY`, `ADMIN_*`,
Redis/Celery keys and other existing application/provider settings.
It must **not** contain `POSTGRES_PASSWORD`,
`KAORI_MIGRATOR_PASSWORD`, `KAORI_RUNTIME_PASSWORD`,
`KAORI_DB_MIGRATION_URL`, `PGPASSWORD` or owner URLs.

The first host initialization generates two additional **ignored
repository-local** development files:

- `secrets/devcontainer/postgres-bootstrap.env`, containing
  `POSTGRES_PASSWORD` and `KAORI_RUNTIME_PASSWORD` for the `db`
  service's initial PostgreSQL identity provisioning.
- `secrets/devcontainer/postgres-migrate.env`, containing
  `KAORI_MIGRATOR_PASSWORD` for `db` initdb and the explicit
  one-shot `db-bootstrap`.

`.devcontainer/examples/` holds tracked sample templates, not real
passwords. `/secrets/` is ignored by Git **and Docker build context**.
The initializer checks the actual PGDATA volume before migrating an
existing local app URL: if the database is empty, it backs up `.env`
under ignored `secrets/devcontainer/` and changes only the runtime
connection plus missing development keys. A populated database with
missing/mismatched credentials is a **hard stop**, not a reason to
generate new passwords or clear Docker volumes. Because the full
checkout is bind-mounted, these files are trusted-development
credentials, **not production-grade secrets isolation**.

See [Environment Configuration](deployment/ENVIRONMENT_CONFIGURATION.md)
for exact file ownership, keys, and production boundaries.

### 2. Open the Dev Container

Open the existing Windows checkout directly in **VS Code Windows** and run
**Dev Containers: Rebuild and Reopen in Container**. Docker Desktop must
be running Linux containers; WSL Remote and Windows Python are unnecessary. The Dev Container compose stack starts PostgreSQL, Redis, the workspace, the canonical Celery workers, and Beat under the isolated **`kaori-dev`** Compose project. `shutdownAction` is `none`, so closing VS Code does not tear down the running development services. Docker restart policies bring them back after a Docker Desktop restart unless they were explicitly stopped.

Do not use plain `docker compose down` for the Dev Container. Host-side development lifecycle commands must use both Compose files:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml down --remove-orphans
```

Do not create or use a host `.venv`; the supported Python runtime is inside the container.

### 3. Initialize or upgrade the database

For a virgin development database, the `db-first-run` Compose service
automatically invokes existing `db-bootstrap` after PostgreSQL role
initialization. This is a one-shot, schema-empty-only operation. The web
debugger (F5) can open the normal login page after bootstrap succeeds;
workers and Beat wait for Alembic, immutable-ledger and admin admission.

Existing or partially initialized databases are **never** automatically
migrated or reset. If first bootstrap fails, examine the job logs and the
**Database Setup Required** recovery command from the Windows host:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs db-first-run
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
```

For later development Alembic upgrades, operator action stays explicit:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml \
  run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
```

No privileged migrator credentials are supplied to normal Flask/workers/Beat.
The application always uses the restricted `kaori_runtime` `DATABASE_URL`.


### 3a. Existing DevContainer databases and the historical role cutover

For **new** PostgreSQL volumes use [the approved three-role fresh setup](operations/devcontainer-postgres-first-run.md).
For older owner-initialized clusters, the [historical #1405 data-preserving cutover](operations/devcontainer-postgres-runtime-role.md) remains a distinct process.
The old `KAORI_DEV_RUNTIME_DATABASE_URL` switch has been retired from
active DevContainer Compose. Never destroy stored data to fix role grants;
request a reviewed migration/back-up workstream.
### 4. Build or watch frontend assets

For active UI development, VS Code runs the `KAORI: Watch Tailwind CSS` background task automatically on folder open after the Dev Container lifecycle completes. Trust the workspace and choose **Allow Automatic Tasks** when prompted. If auto tasks are disabled, use **Terminal → Run Task → KAORI: Watch Tailwind CSS**, or run manually:

```bash
npm run watch-css
```

For a deterministic build:

```bash
npm ci --no-audit --no-fund
npm run build-frontend
npm run verify-frontend
```

### 5. Start the web application

Preferred VS Code path: press `F5` and select **KAORI: Flask Debug**.

Equivalent terminal command inside the Dev Container:

```bash
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

The development application is served at `http://localhost:5000`.

## Development worker verification

KAORI uses dedicated workers/queues. Confirm the expected workers are visible before testing background operations:

```bash
celery --app celery_worker:celery_app inspect ping
celery --app celery_worker:celery_app inspect active_queues
```

Useful targeted checks include:

```bash
python scripts/verify_celery_topology.py
python scripts/verify_reports_worker_runtime.py
```

Artifact Registry Security uses the dedicated `registry-security-worker`. After worker/topology changes, confirm
that `active_queues` shows `registry-security@...` consuming the configured
`REGISTRY_SECURITY_CELERY_QUEUE`; the inventory worker must not consume Security Sync tasks.


If a worker definition or Python dependency changed, rebuild the Dev Container instead of manually drifting an individual service.

## Mode 2 — Governed server Docker Compose (UAT and production)

The deprecated `.env.production.example` is **not** an active environment template and must not be copied into a runtime file. Production uses three independent, host-owned configuration authorities plus generated release identity:

```text
deploy/env/app.env.example      -> /etc/kaori/app.env
deploy/env/secrets.env.example  -> /etc/kaori/secrets.env  (mode 0600)
deploy/env/deploy.env.example   -> /etc/kaori/deploy.env
governed release pipeline      -> /var/lib/kaori/deploy-state/release.env
```

The server deploy adapter merges `compose.production.yml` and `deploy/server/compose.server.yml`, injecting the immutable image digest and exact release identity. The governed GitHub deployment workflow owns **pre-migration backup → environment validation → migration → all application workers/Beat → verification**. Do not run `docker compose -f compose.production.yml up` alone: it bypasses the server overlay and split environment contract.

If authentication schema or database connectivity is unavailable during server
startup, the public **Database Setup Required** screen is a **read-only**
readiness/administrator-notification surface (HTTP 503), not an operator CLI.
It intentionally provides no DevContainer commands or production SQL/migration
instructions. Diagnose and recover through the authorized `deploy/server`
process and its logs, using DBA-managed operations where appropriate.
Migration role separation, guarded first-admin provisioning and external
PostgreSQL lifecycle remain tracked under #621/#1439/#1440; do not infer
their completion from the UI.

After deployment, inspect the existing server runtime through its supported verification entry point:

```bash
bash deploy/server/verify.sh
```

See [`deploy/server/README.md`](../deploy/server/README.md) for bootstrap, delivery, verification, and rollback. Public HTTPS reverse-proxy publication is a separate operator boundary.

## Mode 3 — Local standalone Docker Compose (no Dev Container)

Use [`example/kaori/README.md`](../example/kaori/README.md) for an isolated laptop deployment of an **already admitted RC image**. This does not mount local source and does not run Flask/Tailwind development watchers.

```bash
cd example/kaori
cp .env.example .env
# Replace the immutable KAORI_IMAGE and the matching APP_VERSION, APP_BUILD_SHA,
# APP_BUILD_DATE with exact admitted release evidence. Use disposable local credentials.
bash ./run.sh start
bash ./run.sh status
```

The service port is published only on `127.0.0.1:5000` by default; PostgreSQL and Redis remain Docker-network private. The compact worker consumes the canonical queues (including `registry-security`). For Windows PowerShell commands, see the standalone example README. The `reset` command **deletes standalone data volumes** and is never part of routine startup.

## Release verification

For source/release-candidate verification, use the canonical layered commands:

```bash
python scripts/verify_final_release.py
python scripts/verify_final_release.py --all
python scripts/verify_final_release.py --all --runtime
```

Use `--runtime` only when the required runtime services/workers are actually running. A release tag must not be created until the applicable release gate is green.

## Troubleshooting order

When KAORI does not start or a page returns HTTP 500, investigate in this order:

1. application traceback and missing import/template errors;
2. `flask --app run:app db current` and migration head alignment;
3. PostgreSQL/Redis reachability;
4. environment-contract validation;
5. worker queue availability for background operations;
6. targeted domain test/contract;
7. static quality and final release gates.

Do not bypass a failing release verifier by weakening the verifier or skipping the owning test. Fix the runtime, contract, metadata, or documentation at its canonical ownership boundary.
