# Running KAORI

This document is the canonical entry point for three supported Docker Compose runtime modes:
1. **Local development (Dev Container):** root `.env` + `compose.yml` + `.devcontainer/compose.devcontainer.yml` (`kaori-dev` project, bind-mounted source and VS Code debugging).
2. **Local standalone (no Dev Container):** `example/kaori/.env` + `example/kaori/compose.yml` (`kaori-laptop` project, admitted immutable RC image rather than live local source).
3. **Governed server (UAT/production):** `/etc/kaori/{app,secrets,deploy}.env` + generated `/var/lib/kaori/deploy-state/release.env`, merged `compose.production.yml` + `deploy/server/compose.server.yml` (immutable release and backup/migrate/verify flow).

The files and Docker volumes for these modes are intentionally separate. A root development `.env` must never become the source of production credentials.

## Mode 1 — Local development in VS Code Dev Container

### 1. Prepare the environment

```bash
cp .env.example .env
```

Review at minimum:

- `SECRET_KEY`
- `DATABASE_URL`
- `POSTGRES_*`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- bootstrap `ADMIN_*` values

The complete variable contract is documented in `docs/deployment/ENVIRONMENT_CONFIGURATION.md`.

### 2. Open the Dev Container

Open the repository in VS Code and run **Dev Containers: Rebuild and Reopen in Container**. The Dev Container compose stack starts PostgreSQL, Redis, the workspace, the canonical Celery workers, and Beat under the isolated **`kaori-dev`** Compose project. `shutdownAction` is `none`, so closing VS Code does not tear down the running development services. Docker restart policies bring them back after a Docker Desktop restart unless they were explicitly stopped.

Do not use plain `docker compose down` for the Dev Container. Host-side development lifecycle commands must use both Compose files:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml down --remove-orphans
```

Do not create or use a host `.venv`; the supported Python runtime is inside the container.

### 3. Initialize or upgrade the database

For a fresh development database:

```bash
bash scripts/init_db.sh --bootstrap-admin
```

For an existing development database after pulling migrations:

```bash
flask --app run:app db upgrade
```

On a fresh or migration-behind development database, the workspace remains usable while Celery workers and Beat wait for the exact current Alembic migration head. They do not dispatch or consume scheduled KAORI work before schema readiness and they do not run migrations themselves. After the migration step completes, the background services continue automatically without a manual restart.

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

## Mode 2 — Governed server Docker Compose (UAT and production)

The deprecated `.env.production.example` is **not** an active environment template and must not be copied into a runtime file. Production uses three independent, host-owned configuration authorities plus generated release identity:

```text
deploy/env/app.env.example      -> /etc/kaori/app.env
deploy/env/secrets.env.example  -> /etc/kaori/secrets.env  (mode 0600)
deploy/env/deploy.env.example   -> /etc/kaori/deploy.env
governed release pipeline      -> /var/lib/kaori/deploy-state/release.env
```

The server deploy adapter merges `compose.production.yml` and `deploy/server/compose.server.yml`, injecting the immutable image digest and exact release identity. The governed GitHub deployment workflow owns **pre-migration backup → environment validation → migration → all application workers/Beat → verification**. Do not run `docker compose -f compose.production.yml up` alone: it bypasses the server overlay and split environment contract.

After deployment, inspect the existing server runtime through its supported verification entry point:

```bash
bash deploy/server/verify.sh
```

See [`deploy/server/README.md`](../deploy/server/README.md) for bootstrap, delivery, verification, and rollback. Public HTTPS reverse-proxy publication is a separate operator boundary.

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
