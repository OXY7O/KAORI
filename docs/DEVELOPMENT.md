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

## First setup

1. Copy `.env.example` to `.env`.
   The canonical variable contract is documented in `docs/deployment/ENVIRONMENT_CONFIGURATION.md`.
2. Review `ADMIN_*` and development secret values. Put the separate `postgres_admin_password` and `migrator_password` secret files under the ignored **external WSL host directory** configured by `KAORI_DEV_DB_SECRETS_DIR`; see the [fresh install runbook](operations/devcontainer-postgres-fresh-bootstrap.md). Do not keep PostgreSQL privileged passwords in the application `.env`.
3. Open the repository in VS Code.
4. Run `Dev Containers: Rebuild and Reopen in Container`. **VS Code starts PostgreSQL, Redis, workspace, all ten Celery workers and Beat automatically**. Compose also runs a one-shot `db-role-bootstrap` dependency that creates/adopts the restricted `kaori_runtime` login for a fresh bundled PostgreSQL database. No Docker commands or manual role setup are needed during normal opening.
5. After the Dev Container reports frontend assets are ready, allow VS Code **Automatic Tasks** for this trusted workspace. The existing `KAORI: Watch Tailwind CSS` task starts on folder open, with at most one instance.
6. Press `F5` and select `KAORI: Flask Debug`. A newly created database with no KAORI schema displays the existing **Database Setup Required** page. This is read-only and is expected before first initialization.
7. **Only on the first empty database**, choose **Terminal → Run Task → `KAORI: Initialize Fresh Database`**. This single deliberate task performs non-superuser `kaori_migrator` migrations/RBAC seed, restricted runtime grants, application-admin bootstrap and verifies the Capsule ledger guard. Then refresh the browser to reach normal sign-in. Later DevContainer reopen/start operations require **no database initialization task**.

A fresh or reset `kaori_node_modules` volume must complete `npm ci` and frontend verification before the watcher can work. The `postCreate` lifecycle no longer forces an unconditional global npm upgrade, and `postStart` avoids rebuilding unchanged assets. If lifecycle startup fails, resolve that failure before treating the watcher as ready.

The application is available at `http://localhost:5000`.

### PostgreSQL least-privilege runtime (existing and fresh DevContainer databases)

Capsule Release's immutable ledger requires Flask, Celery workers and Beat
to connect as **non-owner** `kaori_runtime`, using only canonical
`DATABASE_URL`. The DevContainer PostgreSQL bootstrap administrator `postgres` and
non-superuser schema owner `kaori_migrator` have separate secrets
outside the source workspace. The app `.env` owns only the
`kaori_runtime` connection, not `POSTGRES_PASSWORD`.
The explicit VS Code task prompts for the migrator password, then
passes `KAORI_DB_MIGRATION_URL` to a child schema-migration process.
After grants, the first KAORI administrator is created using runtime.
Never persist elevated PostgreSQL credentials in `.env`.

- Existing data: use the [data-preserving runtime-role cutover](operations/devcontainer-postgres-runtime-role.md) for grants/login, guard, backup and rollback.
- Fresh installation: use the [three-identity first-run guide](operations/devcontainer-postgres-fresh-bootstrap.md). VS Code creates all services; the one-shot bootstrap creates PostgreSQL principals **without** running Alembic, then the operator chooses the explicit migration task. The guarded PostgreSQL-only volume reset documented there is a recovery/testing option, **never a required first-run action**.

No source-level owner runtime fallback is admitted. Neither runbook
authorizes production/staging reset or Kubernetes provider mutation.

### Dev Container Compose lifecycle

The development stack uses the isolated Compose project **`kaori-dev`**. VS Code is configured with `shutdownAction: none`, so closing or reloading the editor does not stop PostgreSQL, Redis, Celery workers, or Beat. All development services use restart policies, and Celery workers have queue-appropriate graceful shutdown windows.

Use the merged development Compose definition for host-side lifecycle commands:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs --tail=100
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml down --remove-orphans
```

Do not use plain `docker compose down` to manage the Dev Container.
The plain root Compose project is a separate `kaori` boundary;
the supported development runtime is `kaori-dev` through both files.
**Never use `down -v` or `down --volumes` for a PostgreSQL-only reset**:
that deletes unrelated DevContainer volumes too. Follow the
[scoped fresh-bootstrap procedure](operations/devcontainer-postgres-fresh-bootstrap.md)
only when the developer explicitly authorizes local data destruction.

On a fresh database, VS Code already starts all services through its
existing `runServices` list. The new one-shot Compose service creates only
the non-superuser schema owner `kaori_migrator` and non-owner runtime
login `kaori_runtime`, while PostgreSQL itself initializes `postgres`.
It **never runs Alembic or creates an app administrator**. Workers and Beat are started by DevContainer, but their
existing `WAIT_FOR_SCHEMA=true` gate plus DevContainer-only
`WAIT_FOR_RUNTIME_GRANTS=true` keeps task consumption disabled until the
schema reaches the current Alembic head **and** restricted Capsule ledger
privileges are applied. The initial schema/admin
mutation stays an explicit one-time VS Code task. If opening fails, check
`db-role-bootstrap` logs, configuration and persisted role credentials;
do not reset a nonempty database or silently switch to owner runtime.

Equivalent terminal launch inside the Dev Container:

```bash
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

## Daily workflow

Python and Jinja changes are visible immediately through the bind-mounted source.
The Flask debugger starts without rebuilding the image. Rebuild the Dev Container
only after changing the Dockerfile or Python dependency files.

Useful VS Code tasks:

- `KAORI: Initialize Fresh Database` (one-time explicit fresh schema/RBAC/admin task; non-superuser migrator context is transient)\n- `KAORI: Database Upgrade` (migrator-only migration and restricted-grant refresh)
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
