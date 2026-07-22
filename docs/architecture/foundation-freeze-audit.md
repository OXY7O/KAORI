# KAORI Foundation Freeze Audit

## Scope

This gate covers the cumulative architecture changes from foundation cleanup,
provider persistence authority, registry operation dispatch, Inventory service
modularization, Inventory persistence and synchronization boundaries, collector
modularization, and Inventory overview isolation.

## Enforced Contracts

- `app.integrations.readiness` is the single readiness composition authority.
- Provider binding validation is dispatched through registry operation
  `binding.validate`; validation workers do not import provider validators.
- Integration routes use repository and binding-service boundaries rather than
  querying provider models directly.
- `IntegrationInstance` owns shared provider lifecycle and readiness fields.
- `app.inventory.service` and `app.inventory.collector` remain stable thin
  facades.
- Inventory resource, persistence, synchronization, overview, and collector
  modules follow one-way dependencies.
- Removed legacy modules, templates, and routes must not return.
- The Alembic migration graph must have exactly one head and no missing parent.

## Environment Gate

Static compilation and architecture contracts can run without the application
runtime. Full Ruff and pytest execution must run in the KAORI Dev Container,
where Flask, SQLAlchemy, Celery, Alembic, and the complete development
dependencies are installed.
