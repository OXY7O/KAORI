# Kubernetes Operation Notifications

## CRUD mutation contract

ConfigMap and Secret CRUD operations use two notification paths:

- validation or dry-run feedback is returned immediately through the owning HTMX out-of-band notification response;
- successful Create, Update/Replace, and Delete mutations are queued before `HX-Redirect` or normal redirect, then rendered by the destination page navigation notification region.

A successful mutation must never depend on rendering an OOB fragment after a redirect. Activity Log recording and user notification are both required, but they are separate responsibilities.

Canonical coverage:

- ConfigMap: Create, Update, Delete;
- Secret: Create, Replace, Delete.
