# ConfigMap Operations

## Authoritative live source

ConfigMap operational workflows use Kubernetes as the authoritative source.

```text
Cluster                    -> KAORI Cluster registry
Namespace                  -> live Kubernetes API
ConfigMap identity/content -> live Kubernetes API
Mutation                   -> live Kubernetes API
Inventory                  -> counters and best-effort impact only
```

### Live API methods

- Namespace selector: `CoreV1Api.list_namespace()`.
- Create namespace verification: `CoreV1Api.read_namespace()`.
- ConfigMap selector: `CoreV1Api.list_namespaced_config_map()`.
- Current values and immutable state: `CoreV1Api.read_namespaced_config_map()`.
- Create: `CoreV1Api.create_namespaced_config_map()`.
- Update: `CoreV1Api.patch_namespaced_config_map()`.
- Delete: `CoreV1Api.delete_namespaced_config_map()`.

A ConfigMap created outside KAORI must be selectable immediately. `ConfigurationInventory` is not a target gate. Live lookup errors must be displayed as Kubernetes connectivity, kubeconfig, authentication, namespace, or RBAC errors; the UI must not request an inventory sync before an operation.

All live calls honor the registered cluster TLS settings, including SSL verification and the explicit weak-TLS compatibility option. Selector and object calls use bounded request timeouts so a failed cluster does not leave the operation page hanging indefinitely.

## Target identity

Update and Delete bind the live tuple:

```text
cluster_id + namespace + configmap_name
```

The visible selectors must match the bound tuple. The object is reread live before update or delete so current values, immutable state, and `resourceVersion` are authoritative at execution time.

## Mutation guardrails

- Create verifies the submitted namespace live.
- Create and Update enforce Kubernetes server-side dry-run inside the service boundary before the real mutation.
- Delete validation is strictly non-destructive: KAORI rereads the live target, verifies exact-name confirmation, checks ConfigMap delete authorization with `SelfSubjectAccessReview`, and issues a signed ten-minute receipt without calling the Kubernetes DELETE endpoint.
- Final Delete is the only path that calls `CoreV1Api.delete_namespaced_config_map()`, and it executes once with the validated live `resourceVersion` precondition.
- Create uses create-only semantics and does not overwrite an existing ConfigMap.
- Update includes the live `resourceVersion` in the patch.
- Delete requires exact-name confirmation and uses a `V1Preconditions(resource_version=...)` guard.
- Immutable ConfigMaps cannot be updated.
- Merge and Replace remain explicit update modes.
- Selector failures stay in the filter/workspace and must not become HTTP 500 responses.

## Inventory boundary

Inventory remains a secondary source for:

- landing-page counters;
- historical inventory and reporting;
- best-effort workload dependency context from collected Pod references.

Impact context can lag behind the live object. The UI must label it as inventory-backed and must not represent it as a live dependency query.

## UI contract

- Landing, Create, Update, and Delete use solid KAORI violet heroes with the Inventory Overview geometry.
- Create keeps Target location and Create guardrails side by side.
- Update and Delete mirror the same layout: selector and guardrails first, live editor/impact review below, then final actions.
- After a successful Delete, the cluster, namespace, and ConfigMap selectors are reloaded from the live API; the deleted target is removed immediately and the target/action state is cleared.
- Form controls use 44 px height, 8 px radius, sentence-case labels, shared surface/outline tokens, and violet focus states.
- Descriptive values use compact rectangular labels. Immutable, validation, and destructive conditions use semantic treatments.
- ConfigMap payload fields retain monospace typography.

## Required permissions

- `kubernetes_configmaps.view`
- `kubernetes_configmaps.create`
- `kubernetes_configmaps.update`
- `kubernetes_configmaps.delete`
