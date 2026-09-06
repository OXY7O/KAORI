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

The repository workflow in `.github/workflows/deploy-staging-host.yml` is the staging deployment authority. Do not deploy a mutable branch tag directly to the server.

Persistent Docker volume names retain their established identities so renaming this repository boundary does not orphan existing staging data.
