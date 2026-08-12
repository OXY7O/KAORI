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

- The landing page uses Compact Hero, Live Mutation Evidence Boundary, and Operational Workflow Catalog.
- ConfigMap Management keeps the canonical Hero right context box and workflow catalog. Create, Update, and Delete use the shared **Form + Right Context** layout derived from the Integration registration pattern.
- Form labels use 12 px semibold typography; normal controls use a 40 px minimum height and proportional 14 px values.
- ConfigMap text and binary rows use `components/structured_entry_editor.html`.
- Raw payload fields may retain monospace typography; ordinary identity and configuration values remain proportional.
- Delete keeps best-effort Inventory impact evidence, exact-name confirmation, non-destructive validation, and a final destructive confirmation modal.

## Required permissions

- `kubernetes_configmaps.view`
- `kubernetes_configmaps.create`
- `kubernetes_configmaps.update`
- `kubernetes_configmaps.delete`

## Validated mutation flow

- Create and update forms use the shared validation gate in `app/static/js/validated_operations.js`.
- The final mutation button stays disabled until the latest form state passes validation. Any input or target change invalidates that UI state.
- The server never trusts the browser gate: validation performs one Kubernetes server-side dry-run, while final create and update perform one new server-side dry-run followed by exactly one mutation.
- Successful create, update, and delete operations redirect to a clean page state so cluster, namespace, ConfigMap, entries, and confirmation values do not remain stale.
- Validation failures preserve the current form, replace the persistent validation preview, and append one canonical operational toast without Flask flash messages.

### Validation-gated action state

- Validation-gated ConfigMap actions use `validated_operations.js` as the single client-side state controller.
- Final mutation buttons render in the neutral disabled state until validation succeeds.
- The controller accepts both direct and nested HTMX trigger payloads and also verifies the `HX-Trigger` response header after each request, preventing a successful validation from leaving the final action disabled.
- Any subsequent form input or selection change invalidates the prior validation and disables the final action again.

## Unified KAORI presentation contract

- ConfigMap Management uses `components/operational_workflow_card.html` for natural-height workflow destinations and `components/operation_evidence_boundary.html` for authority context.
- Permission state (`Available` or `Restricted`) is separate from operation classification (`Standard`, `Controlled`, or `Destructive`).
- Create and Update use the reusable validation action bar. Final mutation actions stay neutral and disabled until the latest payload passes validation.
- Dynamic entry handling and cluster/namespace dependency behavior live in `app/static/js/configmap_editor.js`; templates no longer embed imperative `onchange` handlers or per-partial scripts.
- Every ConfigMap hero uses the canonical `page_hero.context_card()` posture panel: one eyebrow/title header, one compact semantic status, two operational metrics, and one full-width contextual CTA. The panel contains no descriptive paragraph and does not own mutation submission.
- Create, Update, and Delete follow the shared **Form + Right Context** standard derived from Register Kubernetes Connection and Register Prometheus/Alertmanager Connection. Geometry is owned by `components/form_with_context_rail.html`; workflow/safety guidance stays secondary, while validation and mutation actions remain in the main task column.

### Shared action-bar contract

- ConfigMap and Secret templates import `components/kubernetes_operation_ui.html`; the former compatibility wrapper is removed.
- The canonical `action_bar` macro owns call-block rendering so validation and mutation controls use one runtime-safe implementation.
- Direct component ownership and wrapper absence are covered by `tests/contracts/kubernetes/test_operation_component_caller_contract.py`.

### Hero navigation and full-width workflow layout

- The ConfigMap Management hero links to Kubernetes cluster management.
- Create, update, and delete workflow heroes return to ConfigMap Management.
- Create, Update, and Delete use `data-kubernetes-operation-layout="form-context-v1"` with operation-specific experience markers while geometry is owned by `components/form_with_context_rail.html`.
- Each operation keeps its own task semantics without copying the shared 8/12 + 4/12 layout classes.
- The Hero right-side context panel remains part of the canonical Hero and is not a content right rail.

## Current KAORI operations pattern

The canonical presentation is documented in `docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md`. Live Kubernetes owns mutation targets, committed Inventory owns best-effort impact context, and Activity Audit owns actor/outcome evidence. Final deletion uses a KAORI destructive confirmation modal without weakening the signed receipt or resourceVersion precondition.


## Workspace density

All ConfigMap CRUD uses the **Form + Right Context** standard. Create uses one primary definition card; Update/Delete keep live target and impact/current-state surfaces in the main 8/12 column while ordered workflow and safety guidance live in the 4/12 context column.


## Canonical service boundaries

ConfigMap Management is split by responsibility:

- `contracts.py` owns typed target, entry, and impact contracts;
- `validation.py` owns DNS/key validation, base64 normalization, update mode, payload sizing, and diff calculation;
- `runtime.py` owns Kubernetes client construction, TLS policy, timeout, and safe provider errors;
- `service.py` owns live lookup and mutation orchestration;
- `receipts.py` owns signed destructive-operation receipts bound to user, target, resource version, and ten-minute expiry;
- `routes.py` owns HTTP, CSRF, Activity Audit, HTMX/OOB response, and redirect behavior.

No internal compatibility aliases or session-stored delete tokens are retained.

## Operational feedback

Every validation and mutation outcome uses `components/operational_toast.html` and the durable Activity Audit event created from the same normalized payload. Success, information, and warning toasts auto-dismiss according to the global policy; errors remain visible until dismissed. Hover or keyboard focus pauses the timer. At most four toasts remain visible.

## Form + Right Context Standard

`Create Kubernetes ConfigMap` is the first Kubernetes Operations consumer of the formal `components/form_with_context_rail.html` geometry. It preserves the proven composition established by Register Kubernetes Connection and Register Prometheus/Alertmanager Connection: one primary form card for `Target & Identity` → `ConfigMap Data` → `Validation` → embedded actions, plus one sticky secondary guidance column containing `ConfigMap Creation Flow` and `Creation Safety Contract`. During the Integrations final recheck, the three registration reference pages should migrate their copied geometry to the same shared component without visual changes. Update and Delete are migrated only after individual browser review.
