<p align="center">
  <img src="app/static/images/kaori-logo.svg" alt="KAORI" width="112" />
</p>

<h1 align="center">KAORI Application</h1>
<p align="center"><strong>Knowledge · Automation · Operations · Resilience · Intelligence</strong></p>
<p align="center">Make infrastructure operations clearer with connected context and trustworthy evidence.</p>

<p align="center">
  <a href="https://github.com/OXY7O/KAORI/actions/workflows/quality.yml">
    <img alt="Full Admission on main" src="https://github.com/OXY7O/KAORI/actions/workflows/quality.yml/badge.svg?branch=main" />
  </a>
  <img alt="Source version line" src="https://img.shields.io/badge/Version-0.3.0-7C3AED" />
  <a href="LICENSE"><img alt="Software source license: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-7C3AED" /></a>
</p>

<p align="center">
  <a href="https://app.kaori.cloud">Application</a> ·
  <a href="https://kaori.cloud">Website</a> ·
  <a href="https://docs.kaori.cloud/">Documentation</a>
</p>

## What is KAORI?

KAORI connects infrastructure inventory, relationships, operational evidence, and governed workflows across tools. It helps operators investigate and coordinate work without replacing authoritative systems such as Kubernetes, Prometheus, or object storage.

This repository contains the **authenticated KAORI Application**, not the public KAORI Website.

## What you can do

- **Observe and relate:** Explore infrastructure inventory, health, and cross-domain context.
- **Analyze and report:** Work from committed operational evidence instead of relying exclusively on live provider requests.
- **Integrate providers:** Connect supported monitoring, infrastructure, and automation capabilities through KAORI's integration registry.
- **Govern operations:** Track decisions, approvals, controlled execution, and audit evidence.

See the [architecture guide](docs/architecture/README.md) for capabilities, data ownership, provider boundaries, and service topology.

## Quick Start

The recommended development environment is the **VS Code Dev Container**. Start Docker Desktop (Linux containers), open this repository in VS Code, and choose **Dev Containers: Reopen in Container**. The first-run setup prepares the local development environment.

Press **F5** to start KAORI. If the application displays **Database Setup Required**, set your local `ADMIN_EMAIL` in `.env`, then run this one-time bootstrap command from **Windows PowerShell on the host**:

```bash
docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml run --rm db-bootstrap
```

Refresh the local sign-in page and use the development admin account configured in your private `.env`. Do not use production credentials.

For setup details and troubleshooting, see [Development](docs/DEVELOPMENT.md) and [PostgreSQL first run](docs/operations/devcontainer-postgres-first-run.md). For an isolated laptop runtime using a pinned release-candidate image, see [Standalone KAORI example](example/kaori/README.md).

## Integration examples

The [examples directory](example/README.md) contains **disposable, local provider labs** for Prometheus, Alertmanager, MinIO/S3-compatible storage, and Thanos Query. These sample stacks help test connectivity; they are **not** the current integration registry, production topology, or a complete list of supported providers.

For real integration behavior and architecture, follow [KAORI architecture](docs/architecture/README.md).

## Deployment & Release

`VERSION` defines the **current product version line**; it is not proof that a stable release has been published or deployed. Routine commits and merges do **not** deploy production.

An intentional stable release requires reviewed release notes, an accepted signed release candidate, explicit operator authorization, and protected production approval. Stable publication preserves the accepted immutable OCI digest rather than rebuilding the application.

See [Changelog](CHANGELOG.md), [Release lifecycle](docs/releases/README.md), and [Release governance](docs/deployment/RELEASE_GOVERNANCE.md) for versions, release history, and operator procedures.

## Contributing, security & license

Changes are reviewed through KAORI's [contribution and delivery standards](docs/engineering/KAORI_DELIVERY_WORKFLOW.md). See [Testing](docs/TESTING.md) for validation instructions. For sensitive findings, use [private security reporting](SECURITY.md), never public issue comments.

KAORI-authored application software source is licensed under [Apache-2.0](LICENSE); see [NOTICE](NOTICE) for attribution and scope. Product names, trademarks, and brand artwork are not covered by the software license; third-party materials retain their own licenses. Source availability does not grant access to hosted services or infrastructure credentials.
