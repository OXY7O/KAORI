# KAORI

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black)
![Status](https://img.shields.io/badge/Status-Active-success)

KAORI is an Infrastructure Operations Observability Platform for Kubernetes
inventory, analytics, intelligence, governance, and management-ready reporting.

## Development

The official development environment is VS Code Dev Containers with Docker
Compose. A host Python virtual environment is not required.

```text
VS Code Dev Container
├── Flask / Python 3.12
├── PostgreSQL 16
├── Redis 7
├── Celery inventory worker
├── Node.js / Tailwind CSS
└── Test, lint, and debug tooling
```

Start here:

1. Copy `.env.example` to `.env`.
2. Open the repository in VS Code.
3. Run `Dev Containers: Rebuild and Reopen in Container`.
4. Run the `KAORI: Database Upgrade`, `KAORI: Seed RBAC`, and
   `KAORI: Bootstrap Admin` tasks.
5. Press `F5` to start Flask.

Detailed instructions: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

## Production

Production uses the immutable `production` Docker target, Gunicorn, and a separate
Celery inventory worker. Database migration is a one-shot service and must run
before the web and worker services are updated.

Detailed instructions: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Core stack

- Python 3.12 and Flask
- PostgreSQL and SQLAlchemy/Alembic
- Redis and Celery background task processing
- Jinja, HTMX, Tailwind CSS, and Alpine.js
- Kubernetes Python client
- Prometheus and Alertmanager integration
- ReportLab PDF generation
- Local and S3-compatible report storage

## Integration compatibility and PromQL profiles

KAORI validates Kubernetes, Prometheus, Alertmanager, and Thanos as separate products. Helm chart metadata is not treated as runtime version evidence. All PromQL is maintained in a versioned query profile with metric, label, retention, deprecation, and replacement metadata.

Technical references:

- `docs/INTEGRATION_COMPATIBILITY.md`
- `docs/PROMQL_QUERY_PROFILES.md`
- `app/prometheus/README.md`
- `app/alertmanager/README.md`
- `app/cluster/README.md`

## Integration domain

Prometheus and Alertmanager configuration now live under the top-level **Integrations** domain rather than Settings or Cluster Management. Kubernetes Cluster Management remains responsible for cluster identity, Kubernetes API connectivity, version/API posture, lifecycle, and inventory synchronization. It only links to integration posture.

Technical references:

- `docs/INTEGRATION_COMPATIBILITY.md`
- `docs/PROMQL_QUERY_PROFILES.md`
- `app/prometheus/README.md`
- `app/alertmanager/README.md`
- `app/cluster/README.md`

### Dashboard and integration navigation

Dashboard navigation is grouped under a reusable **Dashboards** submenu. Kubernetes is the first dashboard; future Server and HCI dashboards should be added to the same submenu rather than creating new top-level sidebar links.

The Integrations Overview is an ecosystem landing page rather than only a combined Prometheus/Alertmanager table. It presents category coverage, a supported/planned catalog, and configured target posture. Planned catalog entries must remain non-actionable until a complete driver and compatibility contract exist. See `app/integrations/README.md`.
