# KAORI DevContainer PostgreSQL — Windows-friendly first-run (#1427)

**Authority:** #1427 and the #1405 immutable Capsule ledger contract. **Scope:** trusted, disposable **local** `kaori-dev` on Docker Desktop. This is not the production/DBA provisioning procedure. Do not apply any local bootstrap command to external PostgreSQL.

## Standard operator workflow

1. Open the existing Windows or Linux checkout directly in **VS Code**, with Docker Desktop running **Linux containers**. Choose **Dev Containers → Rebuild and Reopen in Container**. No WSL Remote or host Python is required, and no manual per-service startup is needed.
2. The VS Code `initializeCommand` invokes `docker run --rm python:3.12-alpine` and mounts the checkout plus the dedicated `kaori-dev_kaori_postgres_data` Docker volume read-only at `/pgdata`. The initializer validates existing `PG_VERSION` before generating database credentials. Absence of a running container is **not** evidence of an empty database volume.
3. On genuinely empty PostgreSQL data, a private root `.env` is generated from `.env.example` if missing. When an **existing local** `.env` already contains a legacy `postgres`/`kaori`/`kaori_runtime` URL to **db:5432/kaori**, it is backed up verbatim to `secrets/devcontainer/application-env-before-three-role.bak`; the connection is replaced with a new restricted `kaori_runtime` URL. All unrelated keys (including integration/provider and admin preferences) are preserved. External/prod URLs are never adopted or rewritten. This step does **not** reset or alter any database.
4. The initializer writes two ignored repo-local credential files. Both are generated automatically, and neither is loaded by a normal Flask/worker/Beat service environment:

   | Local path | Contents | Compose recipient |
   | --- | --- | --- |
   | `<repo>/.env` | `APP_ENV=development`, `POSTGRES_DB=kaori`, `POSTGRES_USER=postgres`, `POSTGRES_PORT=5432`, `DATABASE_URL=postgresql://kaori_runtime:<generated>@db:5432/kaori`, existing KAORI/Redis/integration config, app admin | Workspace/web/10 workers/Beat |
   | `<repo>/secrets/devcontainer/postgres-bootstrap.env` | `POSTGRES_PASSWORD`, `KAORI_RUNTIME_PASSWORD` | PostgreSQL `db` only |
   | `<repo>/secrets/devcontainer/postgres-migrate.env` | `KAORI_MIGRATOR_PASSWORD` | PostgreSQL `db` during first initdb, and explicit `db-bootstrap` only |

   The root `.gitignore` already ignores `/secrets/`, and `.dockerignore` also excludes that directory. Safe tracked templates are `.devcontainer/examples/postgres-bootstrap.env.example` and `postgres-migrate.env.example`. **Actual credentials are never committed or printed.** The entire source tree is bind-mounted into DevContainer, so repo-local ignored files may still be readable to processes with source access. This accepted convenience is limited to trusted local development and must **not** be described as production secrets isolation.
5. Normal Compose starts PostgreSQL, Redis, workspace, ten Celery workers and Beat automatically. The official PostgreSQL 16 entrypoint executes `.devcontainer/postgres-init/01-kaori-roles.sh` **only on an empty PGDATA**: `postgres` bootstrap superuser, `kaori_migrator` non-superuser schema owner, `kaori_runtime` restricted non-owner login. No Alembic application tables or KAORI administrator are created automatically.
6. Press **F5 → KAORI: Flask Debug**, open `http://localhost:5000/auth/login`. Expect **HTTP 503 Database Setup Required / Initialization Required** while the database schema is empty. Worker and Beat services exist but wait for committed Alembic head and runtime permissions.
7. Click **Copy Command** on the existing setup page; execute from **Windows PowerShell on the host at repository root** (or equivalent host terminal):

   ```powershell
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
   ```

   This explicit, profiled one-off `db-bootstrap` uses `kaori_migrator` only for `flask --app run:app db upgrade` and reviewed runtime-grant refresh; it then creates the first KAORI **application administrator** as `kaori_runtime`. It enforces Capsule immutable ledger negative ACLs and read-only `alembic_version` runtime. The application administrator is not a PostgreSQL superuser.
8. Refresh the page, log in with `ADMIN_USERNAME` and private `ADMIN_PASSWORD` in `.env`, and collect real browser/worker/Beat/UAT evidence. **Do not consider a copied command or successful CI alone UAT acceptance.**

## Data preservation and recovery

- If the PostgreSQL data volume contains `PG_VERSION` but either ignored local secret file is missing, the initializer **ABORTS**. It never generates a new owner/migrator password against existing PGDATA. Restore the original matching secrets or use a separately reviewed, data-preserving credential recovery procedure.
- If the volume is partially initialized and nonempty without `PG_VERSION`, it **ABORTS** for manual review.
- If one local credential file exists but its counterpart does not, or the runtime `DATABASE_URL` differs from the recorded `KAORI_RUNTIME_PASSWORD`, it **ABORTS** rather than rotating.
- Legacy local `.env` reconciliation is permitted **only when the PostgreSQL volume is provably empty**. The original file is archived under ignored `secrets/devcontainer/` before changing `DATABASE_URL`. If that backup already exists, operator review is required, not overwrite.
- Reopen with existing database and matching credentials preserves database, roles, application administrator, encryption keys and runtime URL.
- A pre-existing two-role database with owner `kaori` must follow the separate #1405 data-preserving cutover runbook. Never run `docker compose down --volumes` or drop the PostgreSQL volume to make initialization pass.
- For later schema upgrades, use the explicit host command:

  ```powershell
  docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only
  ```

## Technical contract and verification

PostgreSQL runtime is `DATABASE_URL` as `kaori_runtime`, and must not own the database/schema, inherit migrator privileges, perform DDL, mutate `alembic_version`, or `UPDATE`/`DELETE`/`TRUNCATE` Capsule immutable ledgers. The DB server and explicit migration service read only the two development env files they require via scoped Compose `env_file`. On a Windows checkout under OneDrive, the Windows ACLs/sync policy govern the privacy of ignored files; avoid syncing real credentials to shared/cloud-controlled environments.

Read-only inspection before any reset:

```powershell
docker volume ls
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml ps
```

The host pre-init intentionally mounts `kaori-dev_kaori_postgres_data`; Compose treats it as an explicitly named external volume, preventing a surprise rename between `initializeCommand` and actual PostgreSQL startup. The validation gate remains **Developer Check → local Windows fresh-run UAT → human acceptance**, while CI/CD and promotion to `main` remain HOLD until an explicit instruction.

## Production/DBA boundary

Server and DBA-managed PostgreSQL must not use repo-local dev secret files or this bootstrap. Keep normal production runtime as a restricted user and grant separate DBA-owned DDL through #1439/#1440/#1469 (governed SQL migration package, provider evidence, backup/recovery and admission). No real production provider mutation is authorized by this workstream.
