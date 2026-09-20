# KAORI Server Deployment Adapter

`deploy/server/` is the governed host deployment boundary for KAORI. The name is intentionally provider-neutral: the same contract applies to a VPS, dedicated host, virtual machine, or comparable Linux server that meets the documented prerequisites.

The deployment workflow supplies an immutable RC image digest and exact admitted source SHA. The adapter preserves pinned SSH trust, pre-migration backup, database migration, application/worker verification, public HTTPS readiness through the independent shared edge, and retained release-state evidence. Nginx, Certbot, certificate renewal, and host 80/443 are governed separately by `deploy/edge/`.

## Canonical files

- `compose.server.yml` — KAORI server infrastructure overlay and shared-edge consumer attachment.
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

Keep the private key outside the repository and provide it only through the protected GitHub Environment used for UAT deployment. The bootstrap prepares Docker Engine, Docker Compose, the `kaori-deploy` identity, `/opt/kaori`, `/opt/shared-edge`, `/etc/kaori`, and `/var/lib/kaori` without overwriting an existing environment file.

## Server-owned configuration

Real runtime configuration remains on the server under `/etc/kaori/` and is never copied into repository examples. The governed split is `/etc/kaori/app.env`, `/etc/kaori/secrets.env`, and `/etc/kaori/deploy.env`; secrets retain restrictive file permissions. GitHub Secrets provide only the encrypted deployment credentials and pinned SSH trust material needed by the delivery workflow.

The application runtime and release state remain under `/opt/kaori` and `/var/lib/kaori`. Shared ingress/certificate state is owned separately under `/opt/shared-edge`; see `deploy/edge/README.md`.  A temporary UAT installation may share the same physical VPS as a self-hosted `github-runner`, but identities remain separate: runner operations stay under `/opt/actions-runner`, deployment uses `kaori-deploy`, and SSH remains the deployment boundary. See `ops/github-runner/README.md` for the corresponding runner-side trust contract.

The repository workflow in `.github/workflows/deploy-staging-host.yml` is the staging deployment authority. Do not deploy a mutable branch tag directly to the server. Every deployment uses an immutable digest, creates a pre-migration backup when state exists, verifies migrations and runtime health, and retains rollback evidence before public readiness is accepted.

Persistent Docker volume names retain their established identities so renaming this repository boundary does not orphan existing staging data.
