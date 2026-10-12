# KAORI Environment Configuration

KAORI uses one canonical variable inventory with explicit ownership by runtime. The templates are intentionally not identical: development is comprehensive for the Dev Container, the disposable RC-image example is minimal, and production separates application configuration, runtime secrets, deployment-adapter configuration, and generated immutable release identity. Real environment files and credentials must never be committed.

## Three supported runtime modes

| Mode | Runtime configuration | Compose authority | Source behavior |
| --- | --- | --- | --- |
| Local development | Root `.env` and ignored `secrets/devcontainer/{postgres-bootstrap,postgres-migrate}.env` (templates tracked under `.devcontainer/examples/`) | `compose.yml` + `.devcontainer/compose.devcontainer.yml` | Bind-mounted working tree, VS Code debugger, automatic Tailwind watcher and operator-triggered database bootstrap |
| Governed server (UAT/production) | `/etc/kaori/app.env`, `secrets.env`, `deploy.env`, plus generated release state | `compose.production.yml` + `deploy/server/compose.server.yml` | Admitted immutable image digest; pre-migration backup and deployment verification |
| Local standalone Docker | `example/kaori/.env` copied from its own example | `example/kaori/compose.yml` | Admitted RC image; **not** a live-source development build |

The two local modes have separate Compose project names and persistent volumes. Neither local `.env` is a production/server authority. The server has no single monolithic runtime `.env` file.

## DevContainer PostgreSQL first run — ignored repository-local ENV (#1427)

On Windows, use the existing **VS Code Windows → Dev Containers: Rebuild
and Reopen in Container** workflow. No WSL Remote or host Python. The
`initializeCommand` invokes disposable `python:3.12-alpine` using
Docker Desktop. It mounts the source plus **read-only PostgreSQL data
volume `kaori-dev_kaori_postgres_data`** so database existence is
checked using `PG_VERSION`, rather than by counting running containers.

| Configuration authority | Local file | Consumers |
| --- | --- | --- |
| App runtime | Ignored root `.env` from tracked `.env.example`; canonical `DATABASE_URL=postgresql://kaori_runtime:<secret>@db:5432/kaori`; application keys, `ADMIN_*`, integrations, Redis | Flask, workspace, workers, Beat |
| DB initial admin and runtime provisioning | Ignored `secrets/devcontainer/postgres-bootstrap.env`; contains `POSTGRES_PASSWORD` and `KAORI_RUNTIME_PASSWORD` | `db` service only |
| DB schema migration | Ignored `secrets/devcontainer/postgres-migrate.env`; contains `KAORI_MIGRATOR_PASSWORD` | `db` at initial PostgreSQL role creation, `db-bootstrap` when the operator explicitly requests it |

The existing root `.gitignore` excludes `/secrets/`, and
`.dockerignore` excludes that directory from images. Safe tracked
samples are `.devcontainer/examples/postgres-bootstrap.env.example`
and `.devcontainer/examples/postgres-migrate.env.example`. Active
files are generated once with unique random credentials; do not
paste passwords in GitHub, chat or screenshots.

**Fresh-volume reconciliation:** when root `.env` already contains an
older local `DATABASE_URL`, the initializer may replace it **only if
the inspected PostgreSQL volume is empty** and the URL belongs to
`db:5432/kaori`. It first preserves the original application file as
ignored `secrets/devcontainer/application-env-before-three-role.bak`.
All other application/provider configuration stays. If database data
exists or an existing secret file mismatches `.env`, the initializer
**ABORTS**; there is no silent password rotation, volume deletion or
automatic migration.

The PostgreSQL image creates local `postgres` (bootstrap superuser),
`kaori_migrator` (non-superuser schema owner) and `kaori_runtime`
(non-owner restricted DML). Normal app processes retain only canonical
`DATABASE_URL`. Empty schema displays existing HTTP 503
**Database Setup Required / Initialization Required**. Operator runs
the existing copied command from **Windows PowerShell host**:

```powershell
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
```

This migrates as `kaori_migrator`, refreshes runtime/immutable-ledger
grants, and creates first **KAORI application** admin as runtime.
Workers/Beat wait until schema head, ledger and permissions are admitted.
Reopens never implicitly run Alembic or recreate an application admin.

**Security boundary:** these development files are ignored by Git and
Docker build but physically inside a **bind-mounted full repository**;
container processes that can read that workspace may read the files.
Use only in trusted local DevContainer. This is **not** production-grade
credential isolation and must not replace the segregated server
`/etc/kaori/{app,secrets,deploy}.env` or DBA-controlled credentials.
See [the first-run runbook](../operations/devcontainer-postgres-first-run.md).

**Historical local credential-store migration (#1499 → #1500):** a
populated `kaori-dev_kaori_postgres_data` volume plus legacy
`kaori-dev-pg-admin-secrets`/`kaori-dev-pg-migrator-secrets` volumes
can require **manual read-only recovery** of the original role passwords
into the ignored repo-local ENV files. Do not regenerate passwords or
delete PGDATA. The controlled PowerShell command and all preconditions
are documented in the [first-run runbook](../operations/devcontainer-postgres-first-run.md#one-time-recovery-after-upgrading-from-docker-secret-volumes-1499--1500).
This recovery never applies to production or external PostgreSQL.

### Production database authority is separate

Current `deploy/server` behavior is still bundled PostgreSQL + Redis
with migration using existing application environment. The approved
production **target** splits provisioner, migration-only DDL authority,
and restricted runtime for bundled or DBA-external PostgreSQL. DBA-managed
deployments may provide only a restricted runtime login and execute
reviewed SQL changes themselves; no DBA password enters Flask/worker
environments. The external server adapter and DBA SQL migration package
are NOT production-ready just because this DevContainer flow exists.
See [production DBA migration-contract draft PR #1463](https://github.com/OXY7O/KAORI/pull/1463)
and implementation authority #1439/#1440. Existing release/rollback
gates and UAT continue to apply.

## Environment authorities

Use the template that owns the runtime you are configuring:

- `.env.example` is the comprehensive **development / Dev Container** application template. The cross-platform Docker-based `initializeCommand` creates `.env` automatically when absent; operators may copy it first to customize non-secret values and the first administrator email.
- `example/kaori/.env.example` is the intentionally minimal **disposable RC-image** example. It may omit optional settings and relies on safe application defaults baked into the image where appropriate; it is not a production template.
- `deploy/env/app.env.example` owns portable **production application configuration**.
- `deploy/env/secrets.env.example` owns **production runtime secrets**. Example values must remain placeholders; real credentials must not be committed.
- `deploy/env/deploy.env.example` owns **deployment-adapter configuration** used by the production deployment machinery.
- `KAORI_IMAGE`, `APP_VERSION`, `APP_BUILD_SHA`, and `APP_BUILD_DATE` are **generated immutable release identity**. They are supplied by the release process and intentionally do not belong in persistent production templates.
- Optional feature and provider configuration belongs to its documented application authority when enabled; minimal examples may omit it intentionally.

`.env.production.example` is deprecated and inactive. Do not copy it to create a production environment. Production configuration must use the split authorities under `deploy/env/` plus generated release identity.

## Why the templates have different sizes

The Dev Container contract is intentionally comprehensive because engineering needs supported settings to be discoverable and directly overridable during development.

`WAIT_FOR_SCHEMA` is a development/Dev Container orchestration control. The committed development template documents it as `false`, while the Dev Container worker and Beat service definitions override it to `true` so background processing waits for the exact current Alembic migration head. It is not a production application setting; production keeps the governed backup/migration/start sequence.

The disposable RC-image example is intentionally minimal because it runs an already-admitted production image. It overrides only release identity, disposable local credentials/bootstrap values, localhost publication, and proxy trust; reviewed safe application defaults remain owned by application source and the image.

Production is intentionally split by responsibility so portable application policy, runtime secrets, deployment-adapter settings, and generated immutable release identity can change independently without recreating a monolithic environment file.

## Naming contract

Environment-specific prefixes are not used for application settings. The same canonical keys configure report and archive storage in development and production:

- `REPORT_*` controls report storage, staging, delivery, and report worker behavior.
- `ARCHIVE_*` controls reusable archive storage and lifecycle behavior.
- `KAORI_PUBLIC_BASE_URL` is the canonical externally reachable KAORI URL used by generated links and outbound notifications.
- `REGISTRY_SECURITY_*` controls the provider-neutral Artifact Registry Security queue and bounded worker capacity; it is not Harbor-specific.

Legacy `DEV_REPORT_*`, `DEV_ARCHIVE_*`, `PROD_REPORT_*`, `PROD_ARCHIVE_*`, and `REPORT_PUBLIC_BASE_URL` keys are not supported.

## Operational groups

The environment templates document these runtime groups:

- application identity, release metadata, public URL, and integration credential encryption;
- database, Redis, rate limiting, authentication, and reverse-proxy trust;
- Kubernetes Secret reveal and TLS certificate governance windows;
- report/archive storage and data-retention policy;
- integration runtime monitoring and validation workers;
- Artifact Registry security, analytics, forecasting, report, maintenance, and resolver workers;
- Object Storage inventory usage-statistics policy;
- Alert Intelligence notification-dispatch scheduling and delivery retry/timeout controls.

Provider credentials for platform Notification Channels are **not** environment variables. Notification Channels store provider credentials encrypted per channel. `ALERT_INTELLIGENCE_NOTIFICATION_*` and `NOTIFICATION_DELIVERY_*` only control the background dispatcher and provider delivery policy.

Scheduled Reports use reusable Notification Channels configured under Integrations. Provider credentials stay encrypted per channel in the database; report schedules store only selected channel identities.

## Production validation

Before deploying production configuration, populate the split production authorities under `deploy/env/`, supply release identity through the release process, and run:

```bash
python scripts/verify_environment_contract.py
python scripts/validate_production_env.py
```

`verify_environment_contract.py` protects the one-owner split production contract, development contract, local standalone Compose queue/port boundaries, sensitive-key placement, deployment-adapter ownership, generated release identity, and the requirement that `.env.production.example` remain deprecated and inactive. `validate_production_env.py` validates security-sensitive and operational production values such as URLs, credentials, queue names, worker limits, notification delivery controls, and TLS governance windows.
