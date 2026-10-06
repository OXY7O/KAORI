# Domain 5 — Alertmanager Runtime Stabilization

## Objective

KAORI must not select or contact an Alertmanager source after its canonical integration identity becomes disabled or enters a non-active lifecycle state.

## Runtime authority

Operational eligibility is the conjunction of:

- provider record enabled;
- canonical `IntegrationInstance.enabled`;
- canonical `IntegrationInstance.lifecycle_status == active`;
- binding enabled and validated;
- required capability evidence;
- readiness eligibility;
- selector isolation when one source is shared by multiple scopes.

## Worker admission revalidation

Full validation, binding validation, and runtime health refresh re-read the persisted provider record and enforce the operational lifecycle immediately before provider network I/O. This closes the queue race where an operation is admitted and the source is later disabled, deleted, or moved into another lifecycle state before the worker starts.

Binding validation additionally rejects bindings disabled after enqueue.

## Resolver behavior

Alertmanager source resolution includes canonical lifecycle state in eligibility. A source in `deleting`, `disabled`, or another non-active state remains visible in diagnostic candidates but cannot become the selected operational source.

## Deployment

No database migration is required. Existing active integrations continue to resolve normally. Verify that historical rows use `lifecycle_status=active` for operational instances before deployment.

## Rollback

Revert the production and test files in this patch. No data rollback is required.
