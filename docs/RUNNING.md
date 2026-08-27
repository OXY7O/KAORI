# Running KAORI

This document is the canonical operator/developer entry point for starting KAORI. Use the VS Code Dev Container for local development and the immutable release image for production.

## Development quick start

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

### 4. Build or watch frontend assets

For active UI development:

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

If a worker definition or Python dependency changed, rebuild the Dev Container instead of manually drifting an individual service.

## Production startup

Production must use an immutable versioned image and `.env.production` derived from `.env.production.example`.

```bash
cp .env.production.example .env.production
```

Set real secrets and infrastructure endpoints, then ensure `KAORI_IMAGE` and `APP_VERSION` identify the same release.

### 1. Validate environment configuration

```bash
docker compose -f compose.production.yml run --rm validate
```

### 2. Apply database migrations

Back up PostgreSQL first, then run:

```bash
docker compose -f compose.production.yml run --rm migrate
```

### 3. Start the release stack

```bash
docker compose -f compose.production.yml up -d
```

### 4. Verify process and readiness state

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=100 web
```

The web container health check uses `/health/ready`. Also verify queue ownership for inventory, maintenance, runtime, validation, analytics, reporting, forecasting, resolver execution/maintenance, and Beat before approving production readiness.

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
