# KAORI Development Environment

For the canonical start/stop sequence, production startup boundary, and runtime troubleshooting order, see `docs/RUNNING.md`. For the layered test strategy and release commands, see `docs/TESTING.md`.

KAORI development uses VS Code Dev Containers and Docker Compose. Python, Flask,
PostgreSQL, Redis, Node.js, Tailwind, and development linters run inside Linux
containers. A host `.venv` is not required.

## Host prerequisites

- Docker Desktop with the WSL2 backend on Windows, or Docker Desktop on macOS.
- Visual Studio Code.
- VS Code Dev Containers extension.
- Git.
- Docker Desktop with a working Docker CLI on the host; host-side Python is not needed.

## Windows VS Code DevContainer host — supported workflow

KAORI supports the existing workflow: **open the repository directly in
VS Code Windows**, including a checkout under `C:\\Users\\...\\KAORI`,
then choose **Dev Containers: Rebuild and Reopen in Container**.
You do **not** need to open VS Code through WSL Remote or run Python on
the Windows host. Docker Desktop must be running with **Linux containers**.

The `initializeCommand` now starts a small, short-lived
`python:3.12-alpine` container through the normal Docker CLI. This
container prepares private runtime `.env` and two separately
ignored role-credential files under `secrets/devcontainer/` in
the checkout. It also reads the PostgreSQL Docker data volume
**read-only** to distinguish genuinely empty data from an initialized
database. This preserves the standard Windows-host workflow without
putting credentials in source control. It then exits before the
normal DevContainer services start.

When Dev Containers reports an error, inspect the **first failing
command** in the full VS Code Dev Containers log, not only the final
`Exit code 1`. A clean list of running containers does not prove that PostgreSQL
data is absent. Do not delete volumes as a troubleshooting shortcut.

> **Upgrading from the earlier Docker-volume secret implementation?** If
> VS Code Windows initialization reports `existing PostgreSQL data has no
> matching local secrets` while `docker volume ls` still lists
> `kaori-dev-pg-admin-secrets` and `kaori-dev-pg-migrator-secrets`,
> **do not delete the database**. Follow the [one-time, read-only source
> credential recovery](operations/devcontainer-postgres-first-run.md#one-time-recovery-after-upgrading-from-docker-secret-volumes-1499--1500)
> from Windows PowerShell before retrying Reopen in Container.
> The legacy volumes remain intact.

## First setup — new DevContainer PostgreSQL volume

1. Open the project directly in VS Code Windows (or supported Linux/macOS
   Docker host) and choose **Dev Containers → Rebuild and Reopen in Container**.
   The Docker-based host initializer prepares ignored development-only
   credentials and checks PGDATA without host Python or WSL Remote.
2. On empty PGDATA, PostgreSQL 16 creates the separated `postgres`,
   `kaori_migrator` and `kaori_runtime` roles. The automatic `db-first-run`
   one-shot service inspects the local database as migrator and invokes the
   existing guarded `db-bootstrap` only when schema is genuinely virgin.
   It creates Alembic schema, restricted grants, RBAC and first administrator.
3. Press F5 → **KAORI: Flask Debug** and visit `http://localhost:5000/auth/login`.
   When bootstrap succeeds, log in with `ADMIN_USERNAME` and private
   `ADMIN_PASSWORD` in the ignored `.env`. Workers and Beat begin only after
   schema head, immutable-ledger grants and first-admin admission pass.
4. If auto bootstrap fails or finds a non-virgin/partial schema, no data is
   removed or automatically migrated. Inspect from the **host terminal**:

   ```bash
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs db-first-run
   ```

   For an interrupted first install, diagnose the failure and use the
   **Database Setup Required** Copy Command (run from Windows PowerShell
   at the repository root):

   ```bash
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
   ```

   Future migration upgrades remain **explicit** and must use
   `sh scripts/devcontainer/bootstrap-db.sh --upgrade-only`, never
   automatic first-run migration.



**Local ENV layout:** private ignored `.env` stays the normal
application configuration and uses only `kaori_runtime`
`DATABASE_URL`. Privileged PostgreSQL credentials are created under
ignored `secrets/devcontainer/postgres-bootstrap.env` and
`postgres-migrate.env`, with safe `.example` files under
`.devcontainer/examples/`. The initializer backs up an older **local**
`.env` before reconciling its URL **only when the real PostgreSQL
volume is empty**. It refuses a populated database without matching
secrets, without rotating credentials or removing data.

These repo-local secrets are convenient for **trusted development** but
visible to anyone/process with access to the bind-mounted source.
They are never Git-tracked or copied into Docker images; production
continues using separate controlled secrets and DBA migration authority.
See [Environment Configuration](deployment/ENVIRONMENT_CONFIGURATION.md)
and [first-run runbook](operations/devcontainer-postgres-first-run.md).

A fresh or reset `kaori_node_modules` volume must complete `npm ci` and frontend verification before the watcher can work. **Start `KAORI: Watch Tailwind CSS` manually after Dev Container startup reports ready; it never auto-starts on folder open.** The `postCreate` lifecycle no longer forces an unconditional global npm upgrade, and `postStart` avoids rebuilding unchanged assets. If lifecycle startup fails, resolve that failure before treating the watcher as ready.

The application is available at `http://localhost:5000`.

### PostgreSQL least-privilege runtime (existing DevContainer databases)

Capsule Release's immutable START ledger requires the application and all
Celery/Beat workers to use a **non-owner** PostgreSQL role. Older local
databases may have been initialized and used entirely as `kaori` (owner);
that role must not perform the Capsule restart/provider handoff. The
data-preserving, opt-in procedure is documented in
[`DevContainer PostgreSQL runtime-role cutover`](operations/devcontainer-postgres-runtime-role.md).

For a **new** PostgreSQL volume, use the [three-role first-run runbook](operations/devcontainer-postgres-first-run.md).
It automatically provisions `postgres` (local bootstrap), `kaori_migrator`
(non-superuser DDL owner) and `kaori_runtime` (restricted application login)
without creating application tables in PostgreSQL initdb. The guarded
one-shot first-run service initializes virgin schema/admin, and the existing
setup page remains the failure-recovery path. Privileged credentials must
not be loaded into normal worker/Flask environments.

The historical #1405 data-preserving cutover runbook is only for old owner-role
clusters. Its `KAORI_DEV_RUNTIME_DATABASE_URL` override is **not** the active
DevContainer Compose contract. Never delete a database to fix grants.

### Dev Container Compose lifecycle

The development stack uses the isolated Compose project **`kaori-dev`**. VS Code is configured with `shutdownAction: none`, so closing or reloading the editor does not stop PostgreSQL, Redis, Celery workers, or Beat. All development services use restart policies, and Celery workers have queue-appropriate graceful shutdown windows.

Use the merged development Compose definition for host-side lifecycle commands:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs --tail=100
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml down --remove-orphans
```

Do not use plain `docker compose down` to manage the Dev Container. The plain root Compose project is a separate `kaori` boundary; the supported development runtime is `kaori-dev` through the merged files above. Never use `down --volumes` during normal development: a destructive reset requires separate scope and operator authorization.

On a fresh or reset PostgreSQL volume, the workspace remains available immediately, while every Celery worker and Beat waits at the shared database entrypoint until the database reaches the current Alembic migration head. DevContainer creates roles and the guarded db-first-run job applies Alembic **only when the application schema is virgin**. On failed/partial initialization press F5 to view **Initialization Required**, then run `docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap` from Windows PowerShell on the host. Workers/Beat remain gated until schema, immutable-ledger grants and first-admin readiness pass. Future schema upgrades use the same one-off service with `sh scripts/devcontainer/bootstrap-db.sh --upgrade-only`, without recreating the administrator.

Equivalent terminal launch inside the Dev Container:

```bash
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

## Daily workflow

Python and Jinja changes are visible immediately through the bind-mounted source.
The Flask debugger starts without rebuilding the image. Rebuild the Dev Container
only after changing the Dockerfile or Python dependency files.

Useful VS Code tasks:

- `KAORI: Database Upgrade` — now fails closed inside the DevContainer; use the guarded Windows-host PowerShell Docker Compose migrator command
- `KAORI: Database Current`
- `KAORI: Ruff Check`
- `KAORI: djLint Check`
- `KAORI: Watch Tailwind CSS`
- `KAORI: Build Tailwind CSS`
- `KAORI: Developer Check Plan` — resolve the same path-aware validation plan used by GitHub Actions against `kaori/staging`.

### Engineering Evolution v2 development tracks

KAORI supports two context-sensitive inner development loops with one governed delivery outcome:

- **Local-First / Dev Container** — preferred for larger feature work, UI/UX iteration, provider/infrastructure workflows, or broad refactoring where repeated GitHub CI round-trips would dominate feedback time.
- **GitHub-First** — preferred for bounded fixes, documentation, small refactors, and narrow changes where Draft PR Developer Check remains the fastest useful loop.

The tracks do not create separate quality or release paths. Both converge at the frozen-candidate boundary and require exact-head Developer Check, Full Admission, `kaori/staging` integration, applicable UAT, and governed promotion.

For Local-First work, inspect the authoritative plan before candidate freeze:

```bash
python scripts/developer_check_plan.py --base kaori/staging --head HEAD
```

The planner selects existing KAORI validators and focused pytest ownership from the current diff. It does not replace Full Admission. Shared/authority changes widen fail-safe; capability-aware narrowing is introduced only where an explicit test ownership boundary exists.

## Dependency updates

### Toolchain version authority

KAORI targets **Node 22.23.2** and declares **npm 10.9.9** as the package-manager authority in `package.json`. CI and the frontend-image build explicitly install npm 10.9.9. The Dev Container pins Node through its existing locked `ghcr.io/devcontainers/features/node:1` feature; the npm version bundled with that feature may differ (for example, npm 10.9.8). The Dev Container lifecycle deliberately avoids a network-dependent global npm upgrade every time the container is created. `npm ci` installs exactly the committed frontend dependency tree from `package-lock.json`. For intentional lockfile regeneration, use the declared npm 10.9.9 toolchain. Changing the Dev Container feature major requires normal regeneration of `.devcontainer/devcontainer-lock.json`; do not edit the lock by hand.

npm 12.0.2 was reviewed but is deliberately **deferred**. Its Node 22 engine floor is satisfied by Node 22.23.2, but adopting npm 12 would introduce a separate package-manager major lifecycle across Dev Container, CI, and frontend builds. KAORI stays on the latest reviewed npm 10 patch for this maintenance line instead.

Frontend audit also identified Tailwind 4.3.3 and Prettier 3.9.8 as available patch updates. They are **deferred** until their `package-lock.json` changes can be regenerated through the **normal package-manager workflow** inside the aligned Dev Container and verified against generated CSS, formatting, vendor assets, and visual/frontend gates. The lockfile must never be edited manually to force those versions.

Edit `requirements/base.in` for runtime dependencies and `requirements/dev.in`
for development-only tools. Then run inside the Dev Container:

```bash
pip-compile requirements/base.in --output-file requirements/base.txt
pip-compile requirements/dev.in --output-file requirements/dev.txt
```

Rebuild the Dev Container after regenerating either lock file.

For npm dependency changes, update `package.json` and regenerate `package-lock.json` with the pinned package manager:

```bash
npm --version
npm install --package-lock-only
npm ci
npm run prepare-frontend
```

The expected npm version is `10.9.9`; stop if a different package-manager version would rewrite the lockfile.

## Removing the host virtual environment

Delete the Windows or macOS `.venv` only after the Dev Container can start Flask,
run migrations and build Tailwind successfully. The canonical
Python interpreter is `/usr/local/bin/python` inside the container.

## Artifact Registry security worker

Artifact Registry Security uses a dedicated `registry-security-worker` so long-running provider security
collection cannot consume inventory-worker capacity. The worker consumes
`REGISTRY_SECURITY_CELERY_QUEUE` (default `registry-security`) with bounded source-level concurrency.
The fleet job may run multiple Registry instances concurrently, but repository/artifact work remains inside
the provider collector; KAORI does not create one Celery task per artifact.

After pulling a change that adds or modifies this worker, rebuild/reopen the Dev Container. Useful checks:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps registry-security-worker
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs --tail=100 registry-security-worker
celery --app celery_worker:celery_app inspect active_queues
celery --app celery_worker:celery_app inspect registered
```

Expected evidence includes `registry-security@...` consuming `registry-security` (or the configured queue)
and advertising all Artifact Registry Security orchestration/source/finalization tasks.

## Reports worker

The Dev Container starts a dedicated `reports-worker` service automatically. It consumes the queue configured by `REPORTS_CELERY_QUEUE` and identifies itself as `reports@<container-hostname>`. Manual generation, scheduled report dispatch, and generated artifact delivery all use this same queue contract.

After pulling a change that adds or modifies worker services, run **Dev Containers: Rebuild and Reopen in Container**. To start or inspect the service directly from the host:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml up -d reports-worker
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps reports-worker
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs --tail=100 reports-worker
```

From the Dev Container terminal, verify the worker registration and queue subscription:

```bash
python scripts/verify_reports_worker_runtime.py
celery --app celery_worker:celery_app inspect active_queues
```

Expected evidence includes a worker named `reports@...` with the `reports` queue, or the custom queue value configured in `REPORTS_CELERY_QUEUE`. Existing messages retained by Redis begin processing as soon as the worker subscribes.
