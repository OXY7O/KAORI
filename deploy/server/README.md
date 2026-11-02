# KAORI Server Deployment Adapter

`deploy/server/` is the governed host deployment boundary for KAORI. The name is intentionally provider-neutral: the same contract applies to a VPS, dedicated host, virtual machine, or comparable Linux server that meets the documented prerequisites.

The deployment workflow supplies an immutable RC image digest and exact admitted source SHA. The adapter preserves pinned SSH trust, pre-migration backup, database migration, application/worker verification, and retained release-state evidence. Public Nginx/Certbot, certificates, DNS, and host 80/443 are outside the KAORI deployment boundary.

## Canonical files

- `compose.server.yml` — KAORI server infrastructure overlay.
- `deploy.sh` — canonical deployment entry point.
- `bootstrap-host.sh` — one-time host preparation.
- `backup.sh` / `restore.sh` — database backup and restore operations.
- `rollback.sh` — governed rollback support.
- `verify.sh` — internal runtime verification.
- `release-state.sh` — immutable release identity loading.

## Host bootstrap

Generate the deployment key on the operator laptop; the server bootstrap accepts only the public half and never creates or stores the private key:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/kaori-deploy -C kaori-deploy
sudo ./deploy/server/bootstrap-host.sh --ssh-public-key-file ~/.ssh/kaori-deploy.pub
```

Keep the private key outside the repository and provide it only through the protected GitHub Environment used for UAT deployment. The bootstrap prepares Docker Engine, Docker Compose, the `kaori-deploy` identity, `/opt/kaori`, `/etc/kaori`, and `/var/lib/kaori` without overwriting an existing environment file.

## Bundled PostgreSQL identity boundary

The server adapter intentionally retains bundled PostgreSQL/Redis and the
existing `kaori-vps-postgres-data` volume. Bundled production now requires
three independent identities: an existing server bootstrap administrator
(`POSTGRES_USER`), a non-elevated database/schema owner `kaori_migrator`,
and a non-owner application `kaori_runtime`. The administrator secret is
service-scoped in `/etc/kaori/postgres-admin.env`, the migrator URL only in
`/etc/kaori/postgres-migrate.env`, and the runtime URL in
`/etc/kaori/secrets.env`. The one-shot migration service alone receives the
migration file; runtime services cannot inherit privileged PostgreSQL
credentials. Both new files are host-owned, mode 0600 and never embedded
in immutable release records.

A schema-empty bundled database can use the guarded first-run fast path:
set `KAORI_BUNDLED_FRESH_BOOTSTRAP=true` once in the host `deploy.env`,
prepare the two scoped role secrets, and run the existing governed deployment.
After read-only empty-state validation, it creates separate roles, migrates
under the owner, initializes the first administrator as restricted runtime,
and verifies ACL/immutable evidence before web/workers start. Keep the same
PostgreSQL volume; **never** `down -v` or recreate an initialized database.
Set the flag back to false after accepted first-run UAT.

An existing schema, unexpected owner, other active session or ambiguous role
state fails closed and must use the reviewed existing-state path instead.
See [`docs/operations/bundled-postgres-role-cutover.md`](../../docs/operations/bundled-postgres-role-cutover.md)
for first-run configuration, existing-data procedures, recovery and negative
acceptance evidence.

## Server-owned configuration

Real runtime configuration remains on the server under `/etc/kaori/` and is never copied into repository examples. The canonical application/deployment configuration is `/etc/kaori/app.env`, `/etc/kaori/secrets.env`, and `/etc/kaori/deploy.env`; PostgreSQL administrator/migration secret files are separately scoped to their services and retain restrictive file permissions. GitHub Secrets provide only the encrypted deployment credentials and pinned SSH trust material needed by the delivery workflow.

The application runtime and release state remain under `/opt/kaori` and `/var/lib/kaori`. Public exposure is a separate operator concern. An optional standalone reference is documented under `example/shared-edge/`; using it is not part of KAORI release success.  A temporary UAT installation may share the same physical VPS as a self-hosted `github-runner`, but identities remain separate: runner operations stay under `/opt/actions-runner`, deployment uses `kaori-deploy`, and SSH remains the deployment boundary. See `ops/github-runner/README.md` for the corresponding runner-side trust contract.

Runtime worker admission (`verify.sh`) requires the single Beat instance and checks all ten canonical Celery workers by their actual Docker hostname and configured Celery node prefix. One targeted JSON `active_queues` request must receive a nonempty queue list from **every expected worker**; a partial, malformed, or missing response fails the deployment before release state is committed. This retains the immutable image, database privilege, web readiness, backup and rollback checks. It replaces repeated untargeted broadcasts without suppressing any worker's verification. Capture elapsed time only on an authorized RC/UAT host run; the earlier 321-second verification window is a historical baseline, not a promised speedup. If the new destination mapping or broker inspection fails, diagnose safely and roll back the candidate under the existing release procedure; do not bypass admission to force an accepted release.

The repository workflow in `.github/workflows/deploy-staging-host.yml` is the staging deployment authority. Do not deploy a mutable branch tag directly to the server. Every deployment uses an immutable digest, creates a pre-migration backup when state exists, verifies migrations and runtime health, and retains rollback evidence before public readiness is accepted.

Every canonical production application worker, including `registry-security-worker`, must appear in `compose.server.yml` with `env_file: !override` for split `app.env`, `secrets.env`, and generated `release.env`. The server deploy, verification, and database-restore paths must account for the same workers; otherwise Docker Compose can fall back to the deprecated `.env.production` file. The existing UAT deployment contract tests enforce that parity.

Persistent Docker volume names retain their established identities so renaming this repository boundary does not orphan existing staging data.

## PostgreSQL migration authority and DBA-owned databases — pending implementation

The current server adapter still assumes bundled PostgreSQL/Redis and runs the
Compose `migrate` service using existing application environment. **This does
not yet satisfy** the approved separation of runtime PostgreSQL credentials
from migration/DDL authority. Do not present current server mode as supporting
external DBA PostgreSQL or a validated least-privilege migrator.

The approved production target (#621, #622, #1439, #1440) supports two guarded
execution modes: (1) a one-shot migration process with a separate protected
DDL credential, and (2) DBA-executed reviewed SQL when DBAs do not provide
migration passwords. In both cases web/workers/Beat use only a non-owner
`DATABASE_URL`; the DBA owns server, database/role provisioning, HA, backup,
restore and remote storage. A runtime user/password is NOT a grant to perform
DDL, role creation or database backup/restore.

Refer to [DBA and bundled migration contract](../../docs/operations/postgres-dba-migration-contract.md)
for role/access matrix, required SQL package and proof of execution, security
gates and external-provider ownership. Implement this only via #1439/#1440,
with regression and production-like UAT before enabling on the server.
