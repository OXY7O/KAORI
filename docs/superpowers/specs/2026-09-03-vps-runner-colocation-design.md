# KAORI UAT VPS and GitHub Runner Co-location Design

## Context

KAORI currently uses the same VPS for two operational roles during UAT:

1. the self-hosted GitHub Actions runner; and
2. the KAORI application deployment target.

This is a temporary infrastructure constraint, not a reason to merge the two operational domains. The design keeps the deployment interface identical to the future topology where the runner moves to another host.

## Decision

The GitHub runner and KAORI runtime may be physically co-located on one VPS during UAT, but they remain logically and operationally separate.

- Runner operations remain owned by `ops/github-runner/`.
- Application-host preparation and deployment remain owned by `deploy/vps/`.
- The default runner account remains `github-runner` with runner home `/opt/actions-runner`.
- The default deployment account remains `kaori-deploy` with deployment root `/opt/kaori`.
- The deployment account must never be `github-runner` or `root`.
- KAORI environment state remains `/etc/kaori/.env.production`.
- KAORI deploy state and backups remain under `/var/lib/kaori/`.
- Runner workspace, registration state, and runner service lifecycle are not modified by `deploy/vps/bootstrap-host.sh`.

## Deployment trust boundary

The deployment workflow continues to use SSH even when runner and deployment target are currently the same physical VPS.

The workflow must:

- authenticate as `kaori-deploy`;
- use the operator-generated RSA private key stored in GitHub Environment `uat`;
- keep the private key and passphrase off the VPS deployment bootstrap surface;
- verify the target with the reviewed `KAORI_VPS_KNOWN_HOSTS` entry;
- use the configured VPS hostname or IP rather than introducing a localhost-only deployment shortcut;
- execute the existing governed `deploy/vps/deploy.sh` path.

This preserves one deployment interface when the runner later moves to a separate host.

## Docker privilege boundary

Both the self-hosted runner and `kaori-deploy` currently require Docker access. Docker group membership is root-equivalent privilege on the shared VPS.

For UAT, this co-location is accepted as a temporary infrastructure risk with the following constraints:

- distinct Unix identities remain mandatory;
- runner and application paths remain distinct;
- application secrets remain only in `/etc/kaori/.env.production` and GitHub Environment secrets;
- the runner workflow must not read or copy the server-side KAORI environment file;
- the deployment bootstrap must not modify `/opt/actions-runner`, runner registration, runner service files, or runner credentials;
- NGINX, public firewall policy, SSH daemon hardening, and TLS remain Issue #50 scope.

The target production posture is to move the runner to a separate host or runner pool when infrastructure capacity permits. That future move must not require changing the deployment workflow interface.

## Bootstrap behavior

`deploy/vps/bootstrap-host.sh` remains the one-time/idempotent deployment-host bootstrap.

When the shared runner is already present, the bootstrap must preserve it. The bootstrap should explicitly reject `--deploy-user github-runner` and continue to reject `root`, ensuring the two roles cannot collapse into one Unix identity.

The bootstrap continues to prepare only:

- `kaori-deploy`;
- its SSH `authorized_keys` using the operator-provided RSA public key;
- Docker Engine and Compose prerequisites required by deployment;
- `/opt/kaori/releases`;
- `/etc/kaori/.env.production` without overwriting existing contents;
- `/var/lib/kaori/deploy-state`;
- `/var/lib/kaori/backups`.

## Verification

Contract tests must prove:

- co-location is explicitly supported for UAT;
- `ops/github-runner/` and `deploy/vps/` remain separate authorities;
- `github-runner` cannot be selected as the deployment account;
- runner home `/opt/actions-runner` is documented as preserved and outside deployment bootstrap ownership;
- SSH deployment remains the supported path even on the same host;
- private-key, environment, and ingress boundaries remain unchanged.

Developer Check remains the work-branch authority. Comprehensive KAORI CI begins only after merge to `kaori/staging`. A fresh intentional RC must be cut from the newly admitted staging SHA before VPS UAT; `v0.1.0-rc.2` remains historical evidence.
