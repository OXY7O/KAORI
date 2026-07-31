# Kubernetes Secret Management

## Purpose

This domain owns controlled operations against live Kubernetes Secrets. Kubernetes remains the authoritative execution source. KAORI provides target selection, validation, security policy, dry-run enforcement, approval, audit, notification, and best-effort dependency context.

## Authoritative source contract

All operational target selectors use the following boundary:

```text
Cluster                  -> KAORI Cluster registry
Namespace                -> live Kubernetes API
Secret identity/state    -> live Kubernetes API
Mutation/read execution  -> live Kubernetes API
Inventory                -> overview metrics and best-effort context only
```

Inventory records must never block Create, Replace, Reveal, or Delete when the live target is valid. A stale or missing inventory row is not an operational target error.

### Live API methods

- Namespace selection: `CoreV1Api.list_namespace()`.
- Submitted namespace verification: `CoreV1Api.read_namespace()` where the workflow creates a new object.
- Secret selection: `CoreV1Api.list_namespaced_secret()`.
- Selected Secret revalidation: `CoreV1Api.read_namespaced_secret()`.
- Create: `CoreV1Api.create_namespaced_secret()`.
- Replace: `CoreV1Api.patch_namespaced_secret()`.
- Protected Reveal: `CoreV1Api.read_namespaced_secret()` after policy, step-up, and approval controls.
- Delete: `CoreV1Api.delete_namespaced_secret()` with resource-version preconditions.

Live selector failures must remain inside the selector workspace and explain whether the issue is connectivity, kubeconfig, authentication, namespace existence, or RBAC. The UI must not instruct the operator to run inventory synchronization before operating on a live Secret.

## Shared target identity

Replace, Reveal, and Delete identify a Secret using:

```text
cluster_id + namespace + secret_name
```

Replace and Delete bind this tuple when the live editor/review is loaded. The submitted visible selector must match the bound tuple. The selected Secret is read again immediately before validation or execution.

## Mandatory mutation guardrails

1. Create and replace execution perform Kubernetes server-side dry-run inside the service boundary immediately before mutation. Delete validation never calls the Secret DELETE endpoint; it uses live identity review plus SelfSubjectAccessReview authorization preflight.
2. Create uses create-only semantics and never silently overwrites an existing Secret.
3. Replace patches only submitted keys and includes the live `resourceVersion` to detect concurrent changes.
4. Delete requires exact-name confirmation and a live `resourceVersion` precondition.
5. Service-account token Secrets are blocked from the generic Delete workflow.
6. Immutable Secrets cannot be replaced.
7. TLS Secrets use the dedicated TLS rotation workflow rather than generic replacement.
8. Secret material is handled synchronously in request memory and must never be serialized into Celery or Redis.

## Secret payload safety

The Kubernetes Secret list/read APIs can return payload data to the KAORI process. KAORI uses only safe metadata and key names for target selection, then immediately clears payload dictionaries from the in-memory Kubernetes objects.

The application must never:

- render existing Secret values in Create, Replace, Delete, or target selectors;
- persist Secret values, passwords, tokens, registry payloads, private keys, or value hashes;
- include sensitive values in logs, exceptions, notifications, activity metadata, background-job arguments, or analytics;
- return a Secret payload from a list/read helper except through the protected one-time Reveal response.

Protected Reveal is the only plaintext-read workflow. It decodes one approved key, returns a no-store one-time response, clears in-memory buffers, and marks the request consumed.

## Workflow contracts

### Create Secret

- Cluster options come from the KAORI Cluster registry.
- Namespace options are loaded live with `list_namespace()`.
- The submitted namespace is revalidated with `read_namespace()`.
- Supported types: `Opaque`, Basic Auth, TLS, Docker config JSON, and SSH Auth.
- Validate performs server-side dry-run only.
- Create performs server-side dry-run and then the actual create in one service call.
- `NamespaceInventory` and `ConfigurationInventory` are not target gates.

### Replace Secret Data

- Namespace and Secret selectors are live.
- The selected Secret is read live for type, immutability, key names, UID, and resource version.
- Existing values are not rendered or persisted by KAORI.
- Blank existing-key fields preserve the server value because omitted keys are not included in the patch.
- Opaque replacement can update observed keys and add new keys but does not implicitly delete keys.
- Basic Auth can replace username and password independently.
- Docker config JSON replacement is atomic.
- SSH replacement submits one complete private key.
- Apply always dry-runs and then patches the same bound live target.

### Protected Secret Reveal

- Namespace policy rows are based on the live Kubernetes namespace list plus existing policy records.
- New policy access can only be enabled for a namespace that currently exists live.
- Reveal target namespaces are the intersection of enabled policy namespaces and live namespaces.
- Secret and key selection is live.
- Request creation revalidates the selected Secret and key live.
- An optional `configuration_inventory_id` may be stored only as best-effort correlation; it is never a target gate.
- Final reveal rechecks global readiness, namespace policy, Secret type, blocked keys, request ownership/status, expiry, and live key existence.
- One active request is allowed per requester, cluster, namespace, Secret, and key.
- Approval-required requests enforce separation of duties.

### Delete Secret

- Namespace and Secret selectors are live.
- The selected target is reread before validation/execution.
- Workload references from Pod inventory are best-effort impact context only.
- Exact-name confirmation is mandatory.
- Validation rereads the live Secret, verifies exact-name confirmation, records the resource version, and checks effective delete authorization with SelfSubjectAccessReview without calling `delete_namespaced_secret()`.
- Successful validation issues a signed, session-bound receipt valid for ten minutes and tied to cluster, namespace, Secret name, and resource version.
- Final Delete requires and consumes that receipt, rereads the same live target, rejects resource-version drift, and calls `delete_namespaced_secret()` exactly once with a resource-version precondition.
- Service-account token Secrets are excluded from this generic workflow.

### TLS Secret Rotation

TLS rotation remains a specialized workflow because certificate/private-key matching, SAN coverage, expiry posture, and Governance linkage require dedicated validation. Generic Replace and Delete changes must not weaken TLS validation or Protected Reveal boundaries.

## Inventory boundary

Inventory remains valid for:

- Secret Management landing-page counts;
- historical and reporting views;
- best-effort workload references;
- optional correlation from reveal requests to normalized metadata.

Inventory is not authoritative for:

- namespace selection;
- Secret selection;
- key existence;
- type or immutable state at operation time;
- create, replace, reveal, or delete execution.

## Permissions

- `kubernetes_secrets.view`
- `kubernetes_secrets.create`
- `kubernetes_secrets.replace`
- `kubernetes_secrets.delete`
- `kubernetes_secrets.reveal`
- `kubernetes_secrets.approve_reveal`
- `kubernetes_secrets.manage_reveal`
- `kubernetes_secrets.rotate_tls`
- `kubernetes_secrets.bulk_rotate_tls`

After adding or changing permission definitions, run:

```bash
flask seed-rbac
```

The built-in Admin role receives `kubernetes_secrets.delete` through the normal permission seeding policy. Reveal permissions remain separately controlled.

## Route ownership

- `/kubernetes-operations/secrets` — landing page.
- `/kubernetes-operations/secrets/create` — Create Secret.
- `/kubernetes-operations/secrets/replace` — Replace Secret Data.
- `/kubernetes-operations/secrets/delete` — Delete Secret.
- `/kubernetes-operations/secrets/reveal` — Protected Secret Reveal.
- `/kubernetes-operations/secrets/tls-rotation` — TLS rotation.

## Design contract

- Landing uses Compact Hero, Live Mutation Evidence Boundary, and Operational Workflow Catalog.
- Create, Replace, Delete, Reveal, and single TLS Rotation use canonical primary work plus shared Right Context Rail where secondary context is required.
- Form labels use 12 px semibold typography; normal controls use a 40 px minimum height and proportional 14 px values.
- Secret Type uses the responsive Operational Choice Card Group; generic sensitive entries use Structured Entry Editor.
- Validation, approval, expiry, readiness, and destructive states use semantic colors. Operation classification remains separate from permission state.
- Secret material never appears in Hero context, operation summaries, notifications, or Activity Audit metadata.

## Operation feedback and refresh contract

- Validation is non-mutating and returns an HTMX toast without replacing the form or rendering an inline success/error card.
- Create, replace, and delete mutations use POST/Redirect/GET. HTMX mutation responses set `HX-Redirect`; non-HTMX responses use a normal redirect.
- Mutation feedback is queued before redirect so the persistent KAORI toast survives the reload.
- A successful mutation reloads the workflow from live Kubernetes state, clearing stale target selectors, secret payload inputs, validation state, and deleted resources.
- Secret workflows do not use Flask flash messages. Operational outcomes are recorded through the notification and Activity Log pipeline.
- Forms use `hx-sync="this:drop"` and `hx-disabled-elt="find button"` to prevent duplicate concurrent submissions.

## Validated mutation flow

- Create, replace, and delete forms use the shared validation gate in `app/static/js/validated_operations.js`.
- The final mutation button stays disabled until the latest form state passes validation. Any input, uploaded payload, or selected target change invalidates that UI state.
- The server never trusts the browser gate. Create and replace rerun Kubernetes dry-run through `validate_then_apply`; Delete requires a signed, session-bound validation receipt and rejects target or resource-version drift.
- Uploaded Secret streams are rewound between validation and mutation so the exact same payload is applied.
- Successful create, replace, and delete operations redirect to a clean page state, clearing filters, target selection, confirmation values, and sensitive payload inputs.
- Validation failures preserve the current form and use persistent KAORI notifications instead of Flask flash messages.

### Validation-gated action state

- Validation-gated Secret actions use `validated_operations.js` as the single client-side state controller.
- Final mutation buttons render in the neutral disabled state until validation succeeds.
- The controller accepts both direct and nested HTMX trigger payloads and also verifies the `HX-Trigger` response header after each request, preventing a successful validation from leaving the final action disabled.
- Any subsequent form input or selection change invalidates the prior validation and disables the final action again.

## Unified KAORI presentation contract

- Secret Management landing cards, create/replace/delete forms, Protected Reveal surfaces, and TLS rotation use the shared macros in `app/templates/kubernetes_operations/_components.html`.
- Every Secret Management and protected-reveal hero uses the canonical `page_hero.context_card()` posture panel: one eyebrow/title header, one compact semantic status, two operational metrics, and one full-width contextual CTA. Secret payload material is never rendered in the panel.
- Secret Type selection uses `components/choice_card_group.html` with a violet selected boundary, visible check indicator, native radio state, and responsive 1/2/3-column reflow.
- Validation, primary, secondary, destructive, and disabled actions use shared button macros so state changes do not alter geometry or produce thick borders.
- Workflow section headers use one icon container, title hierarchy, description scale, outline, and surface treatment across Create, Replace, Delete, Reveal, and TLS rotation.
- Legacy inline page-size submission handlers are replaced by the global `data-kaori-auto-submit` behavior.
- Secret Type choices do not force a five-card row; desktop uses at most three columns so descriptions remain readable.
- Creation Summary uses reusable operation summary items, while Sensitive Data Policy and Replacement Semantics use the canonical information-guide component.
- Delete and TLS Rotation may use `components/info_flow.html` for secondary procedure context. Protected Reveal uses Tab Style 2 for New Request, My Requests, and Approvals.

### Shared action-bar contract

- ConfigMap and Secret templates import `kubernetes_operations/_components.html` directly; domain-specific component wrappers are not retained.
- Templates that call shared semantic-label macros import `components/table_label.html` explicitly; imported Jinja aliases are not inherited from layouts or sibling partials.
- The canonical `action_bar` macro owns call-block rendering so validation and mutation controls use one runtime-safe implementation.
- Direct component ownership and wrapper absence are covered by `tests/contracts/kubernetes/test_operation_component_caller_contract.py`.

### Hero navigation and workflow layout

- The Secret Management hero links to Kubernetes cluster management.
- Create, replace, delete, reveal, and bulk TLS rotation workflow heroes return to Secret Management.
- Secret creation uses a compact summary list rather than nested summary cards.
- Delete flow and guardrails are grouped inside one sticky right-column wrapper. They must never be separate grid rows, because a sticky flow card would overlap guardrails while the page scrolls.
- Bulk TLS rotation places validation actions below the upload panel; the combined left workflow column aligns with the right rotation-flow panel.

### TLS rotation presentation

- The single TLS Secret rotation hero returns to Secret Management; it does not use an in-page `Open Replacement Form` hero action.
- The rotation workflow uses the canonical target card, replacement-pair upload surface, shared guardrails, shared action bar, and sticky controlled-flow panel.
- Bulk `Target TLS Secrets` uses `components/table.html` and `components/pagination.html` for Inventory-standard header, loading state, filters, Cluster and Namespace identities, semantic status, empty state, Rows Per Page, Previous/Next, and numeric page links.
- Bulk pagination keeps a normal full-page `href` and a separate HTMX `hx-get` partial URL so fallback navigation remains valid and `outerHTML` swaps reinitialize numeric page links.

### Single TLS rotation validation gate

- Single TLS Secret rotation uses the shared `validated_operations.js` gate: `Validate Rotation` performs certificate parsing, private-key matching, SAN coverage review, and target preview without updating Kubernetes.
- Successful validation returns `kaori:operation-validated` for `tls-secret-rotate-form`; only then is `Update TLS Secret` enabled.
- Any certificate or private-key file change invalidates the prior validation and disables Update again.
- The final update endpoint validates the uploaded pair again before mutation, so the browser gate is never treated as an authorization or integrity boundary.
- Specialized TLS validation renders certificate evidence inline because operators must review Common Name, new expiry, SAN coverage, and fingerprint before applying the rotation.
- The right column contains both the controlled flow and the reusable Related Governance Workspace card linking back to the canonical TLS certificate posture.
- Bulk TLS rotation documents a fifth `Validate Outcome` step: review per-target update results and synchronize TLS inventory to confirm the resulting certificate posture.


## Current KAORI operations pattern

The canonical presentation is documented in `docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md`.

- Use the wording **No KAORI Value Persistence**: values are processed transiently and excluded from KAORI persistence, notifications, and Activity Audit metadata.
- Protected Reveal polls only the active segmented workspace and renders one-time material through `components/protected_value_panel.html`.
- Delete requires a final destructive confirmation modal after exact-name entry and non-destructive validation. The modal does not replace the signed receipt, RBAC preflight, target reread, or resourceVersion precondition.
- Reveal registries and bulk TLS tables use scoped endpoint-aware HTMX pagination.
