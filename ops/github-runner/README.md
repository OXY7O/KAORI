# KAORI GitHub Runner Operations

This directory owns host-level operations for the KAORI self-hosted GitHub Actions runner. It is intentionally separate from application `scripts/` and is not application runtime content.

## Operating contract

The supported lifecycle is:

1. `bootstrap-host.sh` — mutate a supported Linux/systemd host to provide Docker Engine + Buildx, the runner service account, and optionally the pinned runner binary.
2. `verify-host.sh` — run independent, read-only, fail-closed host validation before registration or after host maintenance.
3. `config.sh` — perform GitHub runner registration explicitly as an operator from the prepared runner directory.
4. `runner-health.sh` — validate the registered runner service and execution substrate during manual or scheduled health checks.

Registration credentials are never committed here. A GitHub registration token is short-lived operator input and must be obtained immediately before registration.

## Supported host assumptions

- Linux with systemd.
- Debian/Ubuntu through `apt`, or RHEL/CentOS/Rocky/AlmaLinux through `dnf`.
- CPU architecture `x86_64` or `aarch64`/`arm64`.
- Root access for bootstrap only.
- Outbound HTTPS access to GitHub and Docker package repositories.
- Docker Engine with the Buildx plugin.
- Default runner account: `github-runner`.
- Default runner home: `/opt/actions-runner`.

The bootstrap pins GitHub Actions Runner `2.328.0` and validates the archive with an architecture-specific SHA256 before extraction. Override the version only together with the matching reviewed SHA256 values.

## 1. Bootstrap the host

Provision host prerequisites without preparing a runner archive:

```bash
sudo ops/github-runner/bootstrap-host.sh
```

Provision the host and prepare the pinned runner binary:

```bash
sudo ops/github-runner/bootstrap-host.sh --with-runner-binary
```

Bootstrap is intentionally provisioning-only. It does not register a runner and does not install generated verification or health scripts elsewhere on the host.

If a registered runner already exists at the target runner home, binary replacement is blocked. Treat runner upgrades as explicit maintenance rather than an implicit bootstrap side effect.

## 2. Verify the host

Run the independent verifier from the repository checkout:

```bash
ops/github-runner/verify-host.sh
```

The verifier checks Linux/systemd, supported CPU architecture, Docker service/daemon, Buildx, runner account and Docker access, prepared runner binaries, and GitHub connectivity. It does not provision or alter the host.

A disposable Docker smoke test is opt-in because it pulls and executes an external test image:

```bash
ops/github-runner/verify-host.sh --docker-smoke
```

## 3. Register explicitly

Change to the prepared runner directory and use GitHub's registration command shown for the repository or organization. For KAORI, preserve the governed execution labels:

```bash
cd /opt/actions-runner
./config.sh --url https://github.com/OXY7O/KAORI --token '<short-lived-registration-token>' --labels self-hosted,linux,x64,kaori-ci
sudo ./svc.sh install github-runner
sudo ./svc.sh start
```

For an ARM64 host, use the architecture label governed for that runner pool instead of claiming `x64`. Do not copy a registration credential into this repository, shell history, documentation, or persistent environment files.

## 4. Check runner health

After registration and service installation:

```bash
ops/github-runner/runner-health.sh
```

Health checks are non-provisioning and suitable for operator-driven or scheduled execution. A failing result is an operational signal; remediation remains explicit.

## Recovery guidance

- **Docker unavailable:** repair the Docker service first, then rerun `verify-host.sh`.
- **Runner user cannot reach Docker:** review group membership and start a new login/session before changing permissions.
- **Runner binary missing or damaged:** stop the runner service, preserve registration evidence, and perform an explicit runner maintenance procedure. Do not rerun bootstrap over a registered runner.
- **Registration/service missing:** obtain fresh registration material from GitHub, run the explicit registration step, install/start the service, then run `runner-health.sh`.
- **Connectivity failure:** restore outbound HTTPS/DNS/proxy policy before attempting registration or CI work.

## Production image boundary

`ops/github-runner/` is host operations tooling. The KAORI production OCI image uses an explicit runtime allowlist and must not copy this directory into the production stage.
