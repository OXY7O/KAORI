# KAORI

**Knowledge, Automation, Operations, Resilience & Intelligence**

KAORI is an operations platform for Kubernetes and Object Storage environments. It turns committed infrastructure evidence into inventory, Analytics, Reports, Intelligence, Governance, integrations, and controlled operator workflows without replacing the underlying platform authorities.

> KAORI favors evidence over guesswork: operational pages read committed snapshots, live provider calls remain explicit, and release promotion is tied to reviewed source plus immutable artifacts.

## Platform at a Glance

| Capability | What KAORI provides |
| --- | --- |
| Kubernetes Operations | Cluster inventory, nodes, namespaces, workloads, pods, services, ingresses, storage, topology, operational actions, and governed configuration surfaces. |
| Object Storage | Inventory and capacity evidence for S3-compatible environments, including usage, growth, request-path, consumer, and operational posture views. |
| Analytics | Utilization, capacity, forecasting, top consumers, alerts, anomalies, and evidence-backed operational interpretation. |
| Reports | Governed web/PDF report generation, reusable templates, schedules, retained artifacts, and publication evidence. |
| Intelligence | Recommendations, Alert Intelligence, Rule Catalog, accepted-risk/exception workflows, and controlled response evidence. |
| Governance | Kubernetes and platform governance controls with explicit ownership, auditability, and fail-closed boundaries where required. |
| Integrations | Prometheus and Alertmanager provider integrations, with S3-compatible storage and Kubernetes provider adapters. |
| Operational Evidence | Activity Log, notifications, immutable release lineage, validation results, and operator-verifiable runtime evidence. |

## Architecture

KAORI uses a server-rendered application architecture with background workers and provider adapters:

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

Core stack:

- Flask, Jinja, HTMX, and Alpine.js
- PostgreSQL with SQLAlchemy and Alembic
- Redis and Celery
- Kubernetes, Prometheus, and Alertmanager provider adapters
- ReportLab for governed PDF publication
- Local FS and S3-compatible storage backends
- Tailwind CSS with locally built frontend assets

Start with [`docs/architecture/README.md`](docs/architecture/README.md) for the authoritative architecture map.

## Quick Start

The supported development path is the VS Code Dev Container documented in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

Inside the Dev Container:

```bash
cp .env.example .env
bash scripts/init_db.sh --bootstrap-admin
npm run watch-css
flask --app run:app run --host=0.0.0.0 --port=5000 --debug
```

For startup modes, prerequisites, and runtime details, use [`docs/RUNNING.md`](docs/RUNNING.md).

## Quality & Validation

Run the concise release audit:

```bash
python scripts/verify_final_release.py
```

Run the complete release gate before publication:

```bash
python scripts/verify_final_release.py --all
```

Use `--runtime` when the release services are running and live readiness must also be proven. Test ownership and marker conventions are documented in [`tests/README.md`](tests/README.md) and [`docs/TESTING.md`](docs/TESTING.md).

## Deployment & Release

KAORI uses a governed promotion path rather than direct deployment from arbitrary source:

```text
Issue
  → work branch
  → reviewed PR
  → kaori/staging
  → Full Admission
  → intentional RC
  → immutable OCI digest
  → VPS UAT at kaori.cloud
  → explicit UAT acceptance
  → staging-to-main promotion
  → stable SemVer release using the same accepted digest
```

The application image is deployed by immutable digest. A successful CI run, image publication, or technical VPS deployment does not by itself authorize stable promotion. Stable release requires **explicit UAT acceptance** for the exact accepted source SHA and OCI digest, and promotion must not rebuild the accepted application bits.

Production-like VPS deployment uses split operator configuration, a Compose-managed Nginx/Certbot edge, private application/state ports, PostgreSQL backup evidence, controlled migrations, and exact release identity. See [`deploy/vps/README.md`](deploy/vps/README.md) and [`docs/deployment/RELEASE_GOVERNANCE.md`](docs/deployment/RELEASE_GOVERNANCE.md).

## Documentation

Use the repository documentation as the detailed authority rather than duplicating operational contracts here:

- [Architecture](docs/architecture/README.md) — system boundaries, module structure, jobs, quality, and release-surface coverage.
- [Development](docs/DEVELOPMENT.md) — supported developer environment and workflow.
- [Running KAORI](docs/RUNNING.md) — local and runtime startup guidance.
- [Testing](docs/TESTING.md) — test strategy and execution guidance.
- [Deployment](docs/DEPLOYMENT.md) — deployment overview and operational prerequisites.
- [Environment Configuration](docs/deployment/ENVIRONMENT_CONFIGURATION.md) — configuration ownership and environment contracts.
- [Release Governance](docs/deployment/RELEASE_GOVERNANCE.md) — immutable artifact and promotion authority.
- [Current Release Notes](docs/releases/KAORI_2_3_0.md) — canonical notes for the current `APP_VERSION` baseline.
- [KAORI Delivery Workflow](docs/engineering/KAORI_DELIVERY_WORKFLOW.md) — Issue, branch, PR, staging, UAT, and main lifecycle.
- [Changelog](CHANGELOG.md) — recorded product changes.

## Repository Governance

Executable work is governed by an Issue, isolated branch, reviewable PR, work-branch Developer Check, staging integration, and comprehensive post-merge admission. `main` and `kaori/staging` are long-lived authorities; temporary work branches are retired after integration.

Project metadata belongs in GitHub-native Issue/PR/Project fields rather than duplicate metadata tables inside work-item bodies.

## Source Archives

Build source archives only from a clean Git checkout:

```bash
bash scripts/build_source_archive.sh
```

Do not archive an arbitrary working directory containing local or unreviewed state.
