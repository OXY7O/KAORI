# KAORI Server Deployment Adapter

`deploy/server/` is the governed host deployment boundary for KAORI. The name is intentionally provider-neutral: the same contract applies to a VPS, dedicated host, virtual machine, or comparable Linux server that meets the documented prerequisites.

The deployment workflow supplies an immutable RC image digest and exact admitted source SHA. The adapter preserves pinned SSH trust, pre-migration backup, database migration, application/worker verification, HTTPS readiness, TLS/ingress validation, certificate-renewal dry-run, and retained release-state evidence.

## Canonical files

- `compose.server.yml` — server infrastructure and edge overlay.
- `deploy.sh` — canonical deployment entry point.
- `bootstrap-host.sh` — one-time host preparation.
- `backup.sh` / `restore.sh` — database backup and restore operations.
- `rollback.sh` — governed rollback support.
- `verify.sh` — internal runtime verification.
- `release-state.sh` — immutable release identity loading.

## Server-owned configuration

Real runtime configuration remains on the server under `/etc/kaori/` and is never copied into repository examples. The governed split is `/etc/kaori/app.env`, `/etc/kaori/secrets.env`, and `/etc/kaori/deploy.env`; secrets retain restrictive file permissions. GitHub Secrets provide only the encrypted deployment credentials and pinned SSH trust material needed by the delivery workflow.

The application runtime and release state remain under `/opt/kaori` and `/var/lib/kaori`. A temporary UAT installation may share the same physical VPS as a self-hosted `github-runner`, but identities remain separate: runner operations stay under `/opt/actions-runner`, deployment uses `kaori-deploy`, and SSH remains the deployment boundary. See `ops/github-runner/README.md` for the corresponding runner-side trust contract.

The repository workflow in `.github/workflows/deploy-staging-host.yml` is the staging deployment authority. Do not deploy a mutable branch tag directly to the server. Every deployment uses an immutable digest, creates a pre-migration backup when state exists, verifies migrations and runtime health, and retains rollback evidence before public readiness is accepted.

Persistent Docker volume names retain their established identities so renaming this repository boundary does not orphan existing staging data.
