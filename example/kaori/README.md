# Run KAORI on a laptop from an admitted RC image

This example runs the same KAORI production image admitted from `kaori/staging`, but with disposable laptop-local PostgreSQL, Redis, and application state. It does not require the VS Code Dev Container and must not contain staging or production credentials.

## Start

```bash
cd example/kaori
cp .env.example .env
```

Edit `.env` and set `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` from the exact admitted RC evidence. Do not use a mutable `:staging` image.

This example is intentionally smaller than the Dev Container and production environment contracts. It overrides only release identity, disposable local credentials/bootstrap values, localhost publication, and proxy trust. Safe application behavior—such as local report/archive paths, rate limiting, Secret reveal default-deny, report timezone, and automation/custom-runbook default-deny—comes from the reviewed production-image defaults instead of being duplicated here.

Then run:

```bash
./run.sh start
```

Open `http://localhost:5000`. The script starts PostgreSQL and Redis, runs database migrations once, then starts the web process, a compact multi-queue worker, and Celery Beat.

Lifecycle commands:

```bash
./run.sh status
./run.sh logs
./run.sh stop
./run.sh reset
```

`reset` deletes the disposable local database, Redis, and KAORI instance volumes. It never modifies the governed staging server.

For release/deployment authority, see `docs/deployment/RELEASE_GOVERNANCE.md`. This directory is an operator convenience example, not a replacement for Full Admission or the governed staging deployment workflow.
