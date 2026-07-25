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
- Form controls use 44 px height, 8 px radius, sentence-case labels, shared surface/outline tokens, and violet focus states.
- Descriptive values use compact rectangular labels. Immutable, validation, and destructive conditions use semantic treatments.
- ConfigMap payload fields retain monospace typography.

## Required permissions

- `kubernetes_configmaps.view`
- `kubernetes_configmaps.create`
- `kubernetes_configmaps.update`
- `kubernetes_configmaps.delete`

## Validated mutation flow

- Create and update forms use the shared validation gate in `app/static/js/validated_operations.js`.
- The final mutation button stays disabled until the latest form state passes validation. Any input or target change invalidates that UI state.
- The server never trusts the browser gate: final create and update requests run Kubernetes server-side validation again immediately before mutation through `validate_then_apply`.
- Successful create, update, and delete operations redirect to a clean page state so cluster, namespace, ConfigMap, entries, and confirmation values do not remain stale.
- Validation failures preserve the current form and are surfaced through the KAORI notification pipeline without Flask flash messages.

### Validation-gated action state

- Validation-gated ConfigMap actions use `validated_operations.js` as the single client-side state controller.
- Final mutation buttons render in the neutral disabled state until validation succeeds.
- The controller accepts both direct and nested HTMX trigger payloads and also verifies the `HX-Trigger` response header after each request, preventing a successful validation from leaving the final action disabled.
- Any subsequent form input or selection change invalidates the prior validation and disables the final action again.

## Unified KAORI presentation contract

- ConfigMap Management uses the shared Kubernetes operation macros in `app/templates/kubernetes_operations/_components.html` for workflow headers, guardrails, action bars, permission labels, and button states.
- Landing workflow cards mirror Secret Management geometry and hierarchy; destructive actions use semantic critical treatment without changing card dimensions.
- Create and Update use the reusable validation action bar. Final mutation actions stay neutral and disabled until the latest payload passes validation.
- Dynamic entry handling and cluster/namespace dependency behavior live in `app/static/js/configmap_editor.js`; templates no longer embed imperative `onchange` handlers or per-partial scripts.
- The right hero panel contains only status and concise metrics, with no descriptive helper text.

### Shared action-bar wrapper contract

- Domain wrapper macros must declare `caller=None`, capture the outer call-block output before invoking the shared `action_bar` macro, and then pass the captured markup into the shared call block.
- Calling `caller()` directly inside a nested `{% call shared.action_bar(...) %}` block is prohibited because the nested call shadows the outer caller and can raise `jinja2.exceptions.UndefinedError: No caller defined` at runtime.
- The ConfigMap and Secret wrappers share a regression contract test in `tests/contracts/kubernetes/test_operation_component_caller_contract.py`.
