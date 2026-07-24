# KAORI

**Knowledge, Automation, Operations, Resilience & Intelligence**

KAORI is an operations and observability platform for Kubernetes environments. It combines inventory snapshots, Prometheus and Alertmanager integrations, operational analytics, governance controls, reports, recommendations, and controlled remediation workflows.

## Core Stack

- Flask, Jinja, HTMX, and Alpine.js
- PostgreSQL with SQLAlchemy and Alembic
- Redis and Celery
- Kubernetes, Prometheus, and Alertmanager provider adapters
- Tailwind CSS with locally built frontend assets

## Development

The supported development path is the VS Code Dev Container described in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

Initialize a fresh development database:

```bash
bash scripts/init_db.sh
```

Run the complete release gate:

```bash
bash scripts/quality_gate.sh --all
```

The gate validates source hygiene, Python and Jinja syntax, linting and formatting, types and imports, architecture boundaries, runtime import cycles, Celery topology, migrations, permanent tests, and frontend assets.

## Test Taxonomy

- `tests/<domain>/`: permanent functional behavior
- `tests/contracts/`: architecture and ownership contracts
- `tests/migrations/`: migration behavior
- `tests/debug/`: temporary diagnostics excluded from release

See [`tests/README.md`](tests/README.md) for the canonical marker and location rules.

## Architecture Documentation

Start with:

- [`docs/architecture/README.md`](docs/architecture/README.md)
- [`docs/architecture/module-structure.md`](docs/architecture/module-structure.md)
- [`docs/architecture/quality-gates.md`](docs/architecture/quality-gates.md)
- [`docs/architecture/job-execution-foundation.md`](docs/architecture/job-execution-foundation.md)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

## Source Archives

Do not ZIP a working directory. Build a clean source archive from a clean Git checkout:

```bash
bash scripts/build_source_archive.sh
```
