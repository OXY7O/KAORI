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
2. Review `ADMIN_*` and development secret values.
3. Open the repository in VS Code.
4. Run `Dev Containers: Rebuild and Reopen in Container`.
5. Run `bash scripts/init_db.sh --bootstrap-admin` in the Dev Container terminal.
6. Start `KAORI: Watch Tailwind CSS`.
7. Press `F5` and select `KAORI: Flask Debug`.

The application is available at `http://localhost:5000`.

### Dev Container Compose lifecycle

The development stack uses the isolated Compose project **`kaori-dev`**. VS Code is configured with `shutdownAction: none`, so closing or reloading the editor does not stop PostgreSQL, Redis, Celery workers, or Beat. All development services use restart policies, and Celery workers have queue-appropriate graceful shutdown windows.

Use the merged development Compose definition for host-side lifecycle commands:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs --tail=100
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml down --remove-orphans
```

Do not use plain `docker compose down` to manage the Dev Container. The plain root Compose project is a separate `kaori` boundary; the supported development runtime is `kaori-dev` through the merged files above. To intentionally reset the development database and all development volumes, use the same merged command with `down --volumes --remove-orphans`.

Equivalent terminal launch inside the Dev Container:

```bash
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

## Daily workflow

Python and Jinja changes are visible immediately through the bind-mounted source.
The Flask debugger starts without rebuilding the image. Rebuild the Dev Container
only after changing the Dockerfile or Python dependency files.

Useful VS Code tasks:

- `KAORI: Database Upgrade`
- `KAORI: Database Current`
- `KAORI: Ruff Check`
- `KAORI: djLint Check`
- `KAORI: Watch Tailwind CSS`
- `KAORI: Build Tailwind CSS`

## Dependency updates

### Toolchain version authority

KAORI development, CI, and frontend-image builds are aligned on **Node 22.23.2** with **npm 10.9.9**. The Dev Container intentionally preserves its existing locked `ghcr.io/devcontainers/features/node:1` feature digest and pins only the Node version through that feature; `post-create.sh` then installs npm 10.9.9 before any frontend bootstrap. The frontend and CI Docker stages install the same npm version explicitly. Root `package.json` declares `npm@10.9.9` as the package-manager authority. Changing the Dev Container feature major requires regeneration of `.devcontainer/devcontainer-lock.json` through the normal Dev Container tooling and must not be done by hand.

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
