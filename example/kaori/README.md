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

This local standalone Compose stack is not an editable source-code development environment. It pulls the selected approved RC image; changes under the repository working tree do not change the running application. The worker is deliberately compact and consumes all canonical queues, including Artifact Registry Security. Only the web port is bound on the laptop loopback address; PostgreSQL and Redis have no published host ports.

### Windows PowerShell (Docker Desktop, no Dev Container)

Run from `example/kaori` after creating and reviewing `.env`. These Compose commands are an alternative to the Bash `run.sh` wrapper; the wrapper additionally validates the admitted SHA/image reference before start, so retain that approval check when using Compose directly.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set the admitted KAORI_IMAGE, APP_VERSION, APP_BUILD_SHA, APP_BUILD_DATE in .env first.
docker compose --env-file .env -f compose.yml config --quiet
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d postgres redis
docker compose --env-file .env -f compose.yml run --rm migrate
docker compose --env-file .env -f compose.yml up -d web worker beat
docker compose --env-file .env -f compose.yml ps
```

To stop without deleting data, run `docker compose --env-file .env -f compose.yml down`. This mode is for disposable local runtime/UAT checks, **not** a path around approved release gates.

Lifecycle commands:

```bash
./run.sh status
./run.sh logs
./run.sh stop
./run.sh reset
```

`reset` deletes the disposable local database, Redis, and KAORI instance volumes. It never modifies the governed staging server.

For release/deployment authority, see `docs/deployment/RELEASE_GOVERNANCE.md`. This directory is an operator convenience example, not a replacement for Full Admission or the governed staging deployment workflow.
