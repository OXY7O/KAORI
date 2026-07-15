# ConfigMap Operations

## Live operational source

ConfigMap operational workflows use the Kubernetes API as the authoritative source for both namespace and ConfigMap selection.

- Namespace dropdowns are populated with `CoreV1Api.list_namespace()` for the selected cluster.
- ConfigMap dropdowns in View/Update/Delete are populated with `CoreV1Api.list_namespaced_config_map()` for the selected namespace.
- Current ConfigMap values and immutable state are read with `CoreV1Api.read_namespaced_config_map()` before update or delete validation.
- Submitted create namespaces are verified with `CoreV1Api.read_namespace()` before dry-run or mutation.
- A ConfigMap created outside inventory synchronization must be selectable immediately from the operational workflow.
- Inventory snapshots are not used as an operational target gate because create/delete activity can make inventory stale until the next synchronization.

A failed live lookup must be shown as a Kubernetes connectivity, authentication, namespace, or RBAC problem. The UI must not instruct the operator to run inventory synchronization before operating on a live ConfigMap.

## Target identity and mutation guardrail

Update and delete operations identify a ConfigMap with the live tuple:

```text
cluster_id + namespace + configmap_name
```

The editor binds that tuple when current values are loaded. On submit, KAORI compares the visible selector with the bound target and rejects the operation when they differ. This prevents a stale editor from applying data to another ConfigMap after the cluster, namespace, or object selector changes.

## Inventory boundary

Inventory remains a secondary source for:

- management and reporting counters;
- historical inventory views;
- best-effort workload dependency context from collected Pod references.

Impact context can be older than the live object state until inventory synchronization runs. The UI must label this context as inventory-backed and must not represent it as a live dependency query.
