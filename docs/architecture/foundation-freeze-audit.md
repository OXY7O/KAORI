# KAORI Foundation Freeze Audit

## Scope

This gate covers foundation cleanup, provider persistence authority, registry
operation dispatch, Inventory ownership boundaries, report storage contracts,
RBAC authority, route cutover, and removal of internal compatibility layers.

## Enforced Contracts

- `app.integrations.readiness` is the single readiness composition authority.
- Provider binding validation is dispatched through registry operation
  `binding.validate`; validation workers do not import provider validators.
- Integration routes use repository and binding-service boundaries rather than
  querying provider models directly.
- `IntegrationInstance` owns shared provider lifecycle and readiness fields.
- Inventory routes, synchronization, persistence, and collectors import their
  concrete owner modules; aggregate Inventory facades are absent.
- Provider source resolution is fail-closed until binding validation, readiness,
  and required capability evidence satisfy the canonical contract.
- Report artifacts use canonical `local:<object_key>` or `s3:<object_key>` URIs.
- Removed modules, templates, route aliases, product names, and migration shims
  must not return to active application code.
- The Alembic migration graph must have exactly one head and no missing parent.

## Environment Gate

Static compilation and architecture contracts can run without the application
runtime. Full Ruff and pytest execution must run in the KAORI Dev Container,
where Flask, SQLAlchemy, Celery, Alembic, Kubernetes, and the complete
development dependencies are installed.
