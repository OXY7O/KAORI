<p align="center">
  <img src="app/static/images/kaori-logo.svg" alt="KAORI" width="112" />
</p>

<h1 align="center">KAORI</h1>
<p align="center"><strong>Knowledge, Automation, Operations, Resilience & Intelligence</strong></p>
<p align="center">Evidence-driven operations for Kubernetes and S3-compatible infrastructure.</p>

<p align="center">
  <img alt="CI" src="https://github.com/OXY7O/KAORI/actions/workflows/quality.yml/badge.svg?branch=main" />
  <img alt="Version" src="https://img.shields.io/badge/Version-0.2.0-7C3AED" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-internal%20use-64748B" />
</p>

KAORI turns committed infrastructure evidence into Inventory, Analytics, Reports, Intelligence, Governance, integrations, and controlled operator workflows. It complements Kubernetes, Prometheus, Alertmanager, and Object Storage authorities rather than replacing them.

> **Evidence first.** Operational pages use committed snapshots, live provider access stays explicit, and release promotion is bound to reviewed source plus immutable artifacts.

## Architecture

### Platform Capabilities

```text
                         ┌──────────────────────┐
                         │        KAORI         │
                         │ Operations Evidence  │
                         └──────────┬───────────┘
                                    │
           ┌────────────┬───────────┼───────────┬────────────┐
           │            │           │           │            │
      Kubernetes   Object Storage  Reports  Intelligence  Governance
           │            │           │           │            │
           └────────────┴───────────┴───────────┴────────────┘
                                    │
                  Integrations · Automation · Audit
```

The root view intentionally stays product-level. Runtime boundaries, data authority, service topology, workers, provider adapters, and deployment architecture are documented in [`docs/architecture/README.md`](docs/architecture/README.md).

## Quick Start

The supported development path is the VS Code Dev Container described in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

```bash
cp .env.example .env
bash scripts/init_db.sh --bootstrap-admin
npm run watch-css
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

For a laptop that should run a governed staging/RC image **without a Dev Container**, use [`example/kaori`](example/kaori/README.md). The example consumes an explicit admitted image reference rather than a mutable `staging` tag.

```bash
cd example/kaori
cp .env.example .env
# Set KAORI_IMAGE to the exact admitted RC image/tag or digest.
./run.sh start
./run.sh status
```

Runtime modes and prerequisites are documented in [`docs/RUNNING.md`](docs/RUNNING.md).

## Standalone Integration Examples

[`example/`](example/README.md) provides disposable Docker Compose stacks for provider integration testing:

- Prometheus
- Alertmanager
- MinIO / S3-compatible storage
- Thanos Query

Each provider owns its own Compose/configuration surface. `example/compose.demo.yml` is only a convenience topology for exercising multiple providers together. CI runner infrastructure is intentionally outside this integration-example catalog.

## Quality & Validation

```bash
python scripts/verify_final_release.py
python scripts/verify_final_release.py --all
```

Use `--runtime` when release services are running and live readiness must also be proven. See [`docs/TESTING.md`](docs/TESTING.md) and [`tests/README.md`](tests/README.md).

## Deployment & Release

[`VERSION`](VERSION) defines the source-controlled **current product version line**. It is synchronized with the README badge and development fallback, but it is not the exact deployed release identity. Governed prereleases use `vX.Y.Z-rc.N`; deployment strips the leading `v` and injects the exact `APP_VERSION`, source SHA, build date, and immutable image digest. A stable release uses `vX.Y.Z` only after the accepted candidate is promoted without rebuilding application bits.

KAORI uses a governed immutable promotion path:

```text
Issue → Work Branch → Developer Check → kaori/staging → Full Admission
      → immutable RC → staging deployment → explicit UAT acceptance → production promotion
```

A stable release reuses the exact accepted OCI digest; the application image is not rebuilt during stable promotion. Release identity binds source SHA, Git tag, GitHub Release, accepted RC, OCI digest, runtime metadata, signature, and validation evidence.

- [`CHANGELOG.md`](CHANGELOG.md) — product change history and current work.
- [`docs/deployment/RELEASE_GOVERNANCE.md`](docs/deployment/RELEASE_GOVERNANCE.md) — immutable release authority and promotion rules.
- [`docs/releases/KAORI_2_3_0.md`](docs/releases/KAORI_2_3_0.md) — immutable historical 2.3.0 release record; it does not define the current product line.
- [`docs/releases/README.md`](docs/releases/README.md) — canonical release lifecycle and artifact boundaries.
- [`deploy/server/README.md`](deploy/server/README.md) — governed server deployment adapter.

## Security & License

KAORI is currently an **internal-use proprietary project**. It is not distributed under an OSI open-source license and commercial use or redistribution requires explicit authorization. See [`LICENSE`](LICENSE).

Security issues must be reported privately according to [`SECURITY.md`](SECURITY.md). Do not publish credentials, infrastructure addresses, exploitation details, or sensitive operational evidence in public issues.

## Documentation

| Area | Authority |
| --- | --- |
| Architecture | [`docs/architecture/README.md`](docs/architecture/README.md) |
| Development | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| Running KAORI | [`docs/RUNNING.md`](docs/RUNNING.md) |
| Testing | [`docs/TESTING.md`](docs/TESTING.md) |
| Deployment | [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) |
| Release governance | [`docs/deployment/RELEASE_GOVERNANCE.md`](docs/deployment/RELEASE_GOVERNANCE.md) |
| Delivery workflow | [`docs/engineering/KAORI_DELIVERY_WORKFLOW.md`](docs/engineering/KAORI_DELIVERY_WORKFLOW.md) |
| Standalone examples | [`example/README.md`](example/README.md) |

## Repository Governance

Executable work is governed by an Issue, isolated branch, reviewable PR, exact-SHA Developer Check, staging integration, comprehensive Full Admission, and explicit human acceptance before production promotion. `main` and `kaori/staging` are the only long-lived product authorities; temporary work branches are retired after integration.

Real secrets and environment values are never committed to repository examples or release artifacts.
