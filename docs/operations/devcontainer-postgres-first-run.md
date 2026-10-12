# KAORI DevContainer PostgreSQL — Windows-friendly first-run (#1427)

**Authority:** #1427 and the #1405 immutable Capsule ledger contract. **Scope:** trusted, disposable **local** `kaori-dev` on Docker Desktop. This is not the production/DBA provisioning procedure. Do not apply any local bootstrap command to external PostgreSQL.

## Standard operator workflow

1. Open the Windows or Linux checkout in VS Code and run **Dev Containers →
   Rebuild and Reopen in Container** with Docker Desktop Linux containers.
   Host Python and WSL Remote are not needed.
2. The host `initializeCommand` reads the dedicated
   `kaori-dev_kaori_postgres_data` volume read-only. Only when PGDATA is
   genuinely empty can it create fresh ignored `.env` and
   `secrets/devcontainer/{postgres-bootstrap,postgres-migrate}.env`.
   Existing/mismatched data and credentials still fail closed.
3. PostgreSQL `initdb.d/01-kaori-roles.sh` provisions `postgres`,
   non-superuser `kaori_migrator` and restricted `kaori_runtime`.
   It does not create application tables.
4. Compose starts a separate `db-first-run` service automatically.
   Before mutation, it verifies the canonical development `DATABASE_URL`
   and checks as migrator that the schema has **no public relations,
   functions, custom types, nondefault extensions or custom schemas**.
   Only that virgin state invokes the existing `db-bootstrap` script for
   Alembic schema, immutable-ledger grants, RBAC and first admin.
   Existing/partial databases are logged as skipped; no auto migration,
   grant refresh or administrator recreation occurs.
5. Press **F5 → KAORI: Flask Debug**, open
   `http://localhost:5000/auth/login` and sign in. Workers and Beat wait
   until current schema, restricted privileges and first admin are admitted.
   If bootstrap fails, the existing **HTTP 503 Database Setup Required**
   remains the manual recovery surface.
6. Inspect the first-run job from **Windows PowerShell on the host**:

   ```powershell
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml logs db-first-run
   ```

   After diagnosing a partial/failed first-run, use **Copy Command** in
   Database Setup Required or run the original operator-only service:

   ```powershell
   docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
   ```

   Future schema upgrades still require the explicit operator
   `--upgrade-only` command below. Do not delete database volumes or
   regenerate passwords as a troubleshooting shortcut.

   When workers/Beat remain at the schema wait gate after bootstrap,
   distinguish schema migration from restricted-runtime admission.
   The latter checks the PostgreSQL `users.is_active` column (the mapped
   Python attribute is `User.account_is_active`), active nondeleted
   application admin, exact Alembic head, runtime grants and immutable
   Capsule ledger triggers. A worker SQL `UndefinedColumn` is a source
   contract defect, **not** permission to rerun migration, reset PGDATA,
   bypass the gate or grant elevated database privileges. Inspect the
   one-shot `db-bootstrap` output separately from worker and database
   logs; successful migrations alone do not establish ready workers.


## One-time recovery after upgrading from Docker secret volumes (#1499 → #1500)

If **Reopen in Container** aborts with:

`existing PostgreSQL data has no matching local secrets; recovery required`

and `docker volume ls --filter "name=kaori-dev"` shows all three
`kaori-dev-pg-admin-secrets`, `kaori-dev-pg-migrator-secrets`,
and `kaori-dev_kaori_postgres_data`, **do not reset anything**.
The previous three-role implementation stored role passwords inside
those first two Docker named volumes, while the current
DevContainer expects `secrets/devcontainer/*.env` in the ignored checkout.

Run the following one-time **read-only source recovery** from
**Windows PowerShell in the KAORI repository root** after fetching the
review branch with `.devcontainer/recover-legacy-postgres-secrets.py`:

```powershell
docker run --rm `
  --mount "type=bind,source=$($PWD.Path),target=/workspace" `
  --mount "type=volume,source=kaori-dev_kaori_postgres_data,target=/pgdata,readonly" `
  --mount "type=volume,source=kaori-dev-pg-admin-secrets,target=/legacy-admin,readonly" `
  --mount "type=volume,source=kaori-dev-pg-migrator-secrets,target=/legacy-migrator,readonly" `
  -e KAORI_DEV_LEGACY_RECOVERY=1 `
  python:3.12-alpine python /workspace/.devcontainer/recover-legacy-postgres-secrets.py
```

The script refuses recovery unless **all** checks pass:
PostgreSQL 16 `PG_VERSION` exists, both previous volumes contain all
three format-validated, distinct role passwords, and the existing
application `.env` has `APP_ENV=development` and its **exact**
`kaori_runtime` `DATABASE_URL` matches the legacy runtime secret.
It refuses external DB URLs, altered secrets, missing `.env`, mismatched
already-created files or symlinked destinations. This does **not** start
PostgreSQL, change SQL users/passwords, run Alembic, alter `.env`, or
delete any volume. It writes only the two ignored local files
`secrets/devcontainer/postgres-bootstrap.env` and
`secrets/devcontainer/postgres-migrate.env`; previous Docker volumes
stay intact and the command is idempotent if rerun with matching files.
Success output never includes a password.

After `PASS`, retry **VS Code Windows → Dev Containers: Rebuild and
Reopen in Container** without clearing data. This only proves credential
**handoff**, not that the existing cluster contains the expected role
and schema ownership: inspect subsequent PostgreSQL startup/UAT evidence.
If recovery refuses a mismatch, **stop and share only the error text**;
do not invent replacement passwords, delete PGDATA or edit the connection
URL to bypass it.

Because new files are inside the full bind-mounted checkout and on
OneDrive-backed Windows storage, Git-ignore and Docker-build exclusion
do **not** protect them from programs with workspace access or OneDrive
sync. Use this only on the trusted development host; it is not approved
for external/production DBA databases.

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
