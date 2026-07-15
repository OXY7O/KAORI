# ConfigMap Operations

## Live operational source

ConfigMap operational workflows use the Kubernetes API as the authoritative source for namespace selection and namespace validation.

- Namespace dropdowns are populated with `CoreV1Api.list_namespace()` for the selected cluster.
- Submitted namespaces are verified with `CoreV1Api.read_namespace()` before dry-run or mutation.
- Inventory snapshots are not used as an operational namespace gate because create/delete activity can make inventory stale until the next synchronization.
- Inventory remains suitable for reporting, analytics, and best-effort impact context.

A failed live lookup must be shown as a Kubernetes connectivity, authentication, or RBAC problem. The UI must not instruct the operator to run inventory synchronization for operational namespace selection.

## Follow-up boundary

ConfigMap object selection in View/Update/Delete currently retains the existing inventory-backed identity flow. Moving those selectors to fully live object discovery requires a separate target-contract refactor because the current routes and forms identify objects by inventory row ID. Do not silently label those selectors as live until that refactor is completed.
