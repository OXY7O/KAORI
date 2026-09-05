<p align="center">
  <img src="app/static/images/kaori-logo.svg" alt="KAORI" width="112" />
</p>

<h1 align="center">KAORI</h1>
<p align="center"><strong>Knowledge, Automation, Operations, Resilience & Intelligence</strong></p>
<p align="center">Evidence-driven operations for Kubernetes and S3-compatible infrastructure.</p>

<p align="center">
  <img alt="KAORI CI" src="https://github.com/OXY7O/KAORI/actions/workflows/quality.yml/badge.svg?branch=main" />
  <img alt="Release" src="https://img.shields.io/github/v/release/OXY7O/KAORI?display_name=tag&sort=semver" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/license-internal%20use-7C3AED" />
</p>

KAORI turns committed infrastructure evidence into inventory, analytics, reports, intelligence, governance, integrations, and controlled operator workflows. It complements Kubernetes, Prometheus, Alertmanager, and object-storage authorities rather than replacing them.

> **Evidence first.** Operational pages use committed snapshots, live provider access stays explicit, and release promotion is bound to reviewed source plus immutable artifacts.

## ✦ Platform

| Capability | What KAORI provides |
| --- | --- |
| Kubernetes | Inventory, topology, workload and storage visibility, analytics, governed operations, and capacity evidence. |
| Object Storage | S3-compatible inventory, capacity, growth, request-path, consumer, and operational posture views. |
| Intelligence | Recommendations, Alert Intelligence, Rule Catalog, accepted-risk workflows, and controlled response evidence. |
| Reports | Governed web/PDF generation, reusable templates, schedules, retained artifacts, and publication evidence. |
| Governance | Explicit ownership, auditability, policy controls, and fail-closed boundaries where required. |
| Integrations | Kubernetes, Prometheus, Alertmanager, MinIO/S3-compatible storage, and related provider adapters. |

## ⚡ Quick Start

The supported development path is the VS Code Dev Container described in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

```bash
cp .env.example .env
bash scripts/init_db.sh --bootstrap-admin
npm run watch-css
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

Runtime modes and prerequisites are documented in [`docs/RUNNING.md`](docs/RUNNING.md).

## ◈ Standalone Integration Examples

[`example/`](example/README.md) provides disposable **standalone Docker Compose stacks** for integration testing without the private KAORI environment:

- Prometheus
- Alertmanager
- MinIO / S3-compatible storage
- Thanos Query
- disposable GitHub Actions Runner example

Each component owns its own `compose.yml`, environment/configuration surface, lifecycle, and README. `example/compose.demo.yml` is only a convenience topology for exercising several providers together.

```bash
cp example/.env.example example/.env
docker compose -f example/prometheus/compose.yml up -d
docker compose -f example/alertmanager/compose.yml up -d
```

No production host, credential, token, or private environment value is required. Demo/example material is explicitly excluded from production runtime artifacts.

## ◇ Architecture

```text
Browser
  ↓
Flask + Jinja + HTMX
  ↓
Application services / governance / analytics
  ├─ PostgreSQL · committed application and evidence state
  ├─ Redis + Celery · background execution and schedules
  ├─ Kubernetes · cluster/provider operations
  ├─ Prometheus · metrics evidence
  ├─ Alertmanager · alert evidence
  └─ S3-compatible storage · retained report/object artifacts
```

Core stack: Flask, Jinja, HTMX, Alpine.js, PostgreSQL, SQLAlchemy/Alembic, Redis/Celery, WeasyPrint, Kubernetes APIs, Prometheus, Alertmanager, S3-compatible storage, and Tailwind CSS.

The authoritative architecture map lives in [`docs/architecture/README.md`](docs/architecture/README.md).

## ✓ Quality & Validation

```bash
# concise release audit
python scripts/verify_final_release.py

# complete admission gate
python scripts/verify_final_release.py --all
```

Use `--runtime` when release services are running and live readiness must also be proven. See [`docs/TESTING.md`](docs/TESTING.md) and [`tests/README.md`](tests/README.md).

## ⬢ Release & Distribution

KAORI uses a governed immutable promotion path:

```text
Issue
  → Work Branch
  → Developer Check
  → kaori/staging
  → Full Admission
  → Staging Validation
  → Staging Acceptance
  → Production Promotion
  → Stable SemVer Release
```

A stable release reuses the exact accepted OCI digest; the application image is **not rebuilt** during stable promotion. Release identity binds the Git tag, GitHub Release, source SHA, accepted RC, Docker Hub version tag, OCI digest, runtime metadata, signature, and validation evidence.

- [`CHANGELOG.md`](CHANGELOG.md) — product change history and current `[Unreleased]` work.
- [`docs/deployment/RELEASE_GOVERNANCE.md`](docs/deployment/RELEASE_GOVERNANCE.md) — immutable release authority and promotion rules.
- [`docs/releases/`](docs/releases/) — historical/detail release records.
- GitHub Releases — stable release notes and release assets.

The production OCI image and downloadable runtime package are application-only boundaries. Tests, examples, CI metadata, docs, development tooling, and private environment content do not belong in the runtime payload.

## 🔒 Security & License

KAORI is currently an **internal-use proprietary project**. It is not distributed under an OSI open-source license and commercial use or redistribution requires explicit authorization. See [`LICENSE`](LICENSE).

Security issues must be reported privately according to [`SECURITY.md`](SECURITY.md). Do not publish credentials, infrastructure addresses, exploitation details, or sensitive operational evidence in public issues.

## 📚 Documentation

| Area | Authority |
| --- | --- |
| Architecture | [`docs/architecture/README.md`](docs/architecture/README.md) |
| Development | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| Running KAORI | [`docs/RUNNING.md`](docs/RUNNING.md) |
| Testing | [`docs/TESTING.md`](docs/TESTING.md) |
| Deployment | [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) |
| Environment configuration | [`docs/deployment/ENVIRONMENT_CONFIGURATION.md`](docs/deployment/ENVIRONMENT_CONFIGURATION.md) |
| Release governance | [`docs/deployment/RELEASE_GOVERNANCE.md`](docs/deployment/RELEASE_GOVERNANCE.md) |
| Delivery workflow | [`docs/engineering/KAORI_DELIVERY_WORKFLOW.md`](docs/engineering/KAORI_DELIVERY_WORKFLOW.md) |
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |
| Standalone examples | [`example/README.md`](example/README.md) |

## Repository Governance

Executable work is governed by an Issue, isolated branch, reviewable PR, work-branch Developer Check, staging integration, comprehensive Full Admission, and explicit acceptance before production promotion. `main` and `kaori/staging` are the only long-lived product authorities; temporary work branches are retired after integration.

GitHub-native Issue/PR/Project fields remain the metadata authority. Real secrets and environment values are never committed to repository examples or release artifacts.
