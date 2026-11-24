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

## Environment-selected deployment target identity (App #5093 / #5094)

The protected `kaori/staging` branch routes its admitted signed RC to GitHub Environment `staging`. Protected `main` uses GitHub Environment `production` for independently approved stable publication. **An Environment is not a runtime slot count.** The operator configures the effective host, pinned SSH key/known-hosts, Compose project/service identity, deployment root, state/receipt, database/volume and network ownership, and provider-owned ingress. Multiple Environments can share an effective runtime; a single VM/IP can host more than one isolated runtime.

**Current tested default:** `kaori-production` Compose project, network, bundled PostgreSQL/Redis volumes, host config `/etc/kaori`, state `/var/lib/kaori/deploy-state`, backup `/var/lib/kaori/backups`, release root `/opt/kaori`, existing `app.kaori.cloud` edge. These are the present host configuration and rollback baseline, **not a release policy requiring a single server**. GitHub `KAORI_HOST*` variables select the remote VM and release root; the VM-local `/etc/kaori/deploy.env` remains the canonical configuration authority. For an explicitly provisioned alternate App runtime root `/opt/kaori/targets/<project>`, the workflow derives `/etc/kaori/targets/<project>/deploy.env` from the existing `KAORI_HOST_DEPLOY_ROOT` value—**no extra GitHub Environment variable**. The #5093 source adapter now accepts bounded `KAORI_COMPOSE_PROJECT`, network, instance/PostgreSQL/Redis volume, state, backup, trust and release-root settings, and validates their consistency **before Docker/database mutation**. A distinct runtime uses a reserved `kaori-app-*` project and separately prepared `/etc/kaori/targets/<project>`, `/var/lib/kaori/targets/<project>` and `/opt/kaori/targets/<project>` roots. Reusing a canonical database volume or state receipt under a distinct project is rejected.

**Operational UAT caveat (2026-11-22):** the #5093 target-selector source has been independently reviewed and admitted through protected `kaori/staging` and `main`, with both protected Environment registry/SSH/receipt read-only preflights PASS. **A distinct configured runtime has not received non-public deployment, database/volume isolation, health, recovery/rollback, provider-edge or Human UAT acceptance.** It does not provision a new host, initialize a target database automatically, or register a different public ingress. The shared-edge workflow deliberately refuses a distinct project until its provider-owned routing has separate approval. Simply changing a host/IP is **not** sufficient to prove operational target isolation. Issue #5094, blocked by #5093, will reconcile the signed Human Accepted digest to the **configured** `production` target: if already healthy at that digest with correct receipt, avoid a second deploy; otherwise deploy the same signed digest through the reviewed adapter only after target/rollback/provider-edge gates. No `single-slot`/`multi-slot` toggle, host-IP-count inference, implicit DNS change or new release engine.

The accepted `v0.3.0-rc.1` source, digest and owner Human Acceptance must not be silently reused to claim UAT of a later runtime-target adapter. Source admission and successful read-only Environment connectivity do not qualify a newly configured target for release. Until actual non-public operational UAT is completed and accepted, current-target behavior remains the only operationally verified path.

## Production provider trust and internal DNS

The governed server adapter mounts externally approved **public CA bundles**
from `/etc/kaori/trust` to `/run/kaori/trust`, read-only, for
`web`, `validation-worker` and `runtime-worker` only. The initial host
bootstrap creates the empty directory, **never a certificate or private key**.
Compose long bind syntax uses `create_host_path: false`; existing
servers that were initialized before this feature must provision the
empty directory before applying this newer Compose contract.
The base `/app/instance` named volume remains unchanged.

Optional trust/allowlist settings belong to `/etc/kaori/app.env` using
the safe blank values documented in `deploy/env/app.env.example`. LDAP
service-account credentials remain only in `secrets.env`. Corporate DNS
and directory PKI are authoritative; do not turn lab-only
`secrets/devcontainer/compose.host-overrides.yml` into the production
deployment input. The certificate currently used in local LDAP UAT was
self-signed without observed `CA:TRUE`; a successful local TLS handshake
does not approve it for normal production CA distribution.

See [Production internal DNS and provider CA trust](../../docs/operations/production-provider-dns-trust.md)
for the full operational configuration, certificate checks, render
inspection, service-scoped restart, rollback and future Kubernetes
reference. This change is not a live host deployment or DNS mutation.

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

The repository workflow in `.github/workflows/deploy-staging-host.yml` is the staging deployment authority. It is **manual-only** on the current protected `kaori/staging` SHA with an explicit signed candidate tag; neither `kaori/uat-request` pushes nor ordinary source commits deploy this host. The existing configured staging target can be the same canonical runtime as production: operators must separately authorize any shared-host impact or verify a genuinely isolated target before dispatch. Do not deploy a mutable branch tag directly to the server. Every deployment uses an immutable digest, creates a pre-migration backup when state exists, verifies migrations and runtime health, and retains rollback evidence before public readiness is accepted.

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

## Bundled OpenBao candidate (not yet deployment-admitted)

See [OpenBao PostgreSQL profile](openbao/README.md) under #5202/#5200. This candidate does not modify the canonical deploy.sh path, does not start an OpenBao service automatically, and does not migrate current ENV configuration. PostgreSQL database/role/TLS, immutable image, initialization and recovery admission must pass before integration into the canonical bundle.
