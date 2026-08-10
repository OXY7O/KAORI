# Kubernetes ConfigMap and Secret Operations

## Scope

This pattern applies to:

- ConfigMap Management, Create, Update, and Delete;
- Secret Management, Create, Replace, Delete, Protected Reveal, and TLS Rotation.

## Canonical landing composition

```text
Compact Hero
Live Mutation Evidence Boundary
Operational Workflow Catalog
```

The landing page is an operations catalog, not a marketing-card grid. Workflow cards use natural height and separate permission state from operation classification.

## Live Mutation Evidence Contract

Every mutation workspace distinguishes three authorities:

| Evidence | Authority |
|---|---|
| Target identity, namespace, current object data, key names, values, and resourceVersion | Live Kubernetes API |
| Known consumers and impact context | Current committed Inventory snapshot |
| Actor, request, validation, decision, and outcome | KAORI Activity Audit |

Inventory impact evidence is best effort. It must not be described as complete dependency analysis.

## Canonical Mutation Workspace — Task-Fit Layout v7

```text
Management / Registry
→ Hero + right context accessory + workflow catalog

Ordinary CRUD mutation
→ Main task workspace + shared compact right context rail
→ validation evidence + canonical action bar remain in the main task

Protected Reveal New Request
→ shared Form + Right Context request task

Protected Reveal registries / TLS
→ dedicated reviewed composition
```

Rules:

- choose layout by task semantics instead of applying one geometry to every Operations page;
- ConfigMap Management and Secret Management retain their canonical Hero context box and workflow catalog;
- ordinary CRUD forms should use the shared **Form + Right Context** layout when a supporting right column materially improves scanability; geometry is owned by `components/form_with_context_rail.html` and must not be copied into newly reviewed templates;
- the secondary column is limited to concise reusable guidance such as one primary `info_flow` and one secondary guide; it must use intrinsic height and never contain the mutation action itself;
- the primary form should be one canonical form card with internal sections rather than a stack of independent mutation cards; validation and the canonical action bar remain inside that primary card;
- do not introduce a new page-local geometry when the shared Form + Right Context or another reviewed KAORI pattern already fits;
- controls use 40 px geometry and 12 px labels;
- mutation remains validation-gated, but the server always performs a fresh provider validation immediately before mutation;
- target identity, payload/current state, validation evidence, and destructive impact remain visually distinct rather than becoming one stretched card;
- the canonical Hero may still own a right-side Context/Status/Action accessory; that Hero accessory is not a content right rail;
- light/dark, keyboard focus, HTMX loading, error states, and 14-inch/narrow responsive behavior are mandatory.

### Request security order

Every protected Kubernetes Operations route follows:

```text
Authentication
→ RBAC permission
→ cluster prerequisite
→ CSRF / request validation
→ live Kubernetes read or mutation
→ Activity Audit / Operational Feedback
```

The canonical boundary is **AuthZ → cluster prerequisite → request validation → live provider**. The cluster prerequisite is implemented with `cluster_required()` inside the route permission boundary. A Blueprint `before_request` must not return cluster onboarding/readiness responses before authorization.


## ConfigMap entry editing

ConfigMap text and binary entries use Structured Entry Editor. Update keeps Merge and Replace explicit. Immutable ConfigMaps remain protected from update.

## Secret creation and replacement

Secret Type uses Operational Choice Card Group with the canonical responsive 1/2/3-column reflow. The selected option uses a strong Violet boundary, selected surface, check icon, and explicit `Selected` marker; changing only the rail summary is insufficient. Existing values are never rendered in Replace. Blank replacement inputs mean unchanged; submitted values mean replace.

Use the wording `No KAORI Value Persistence`: values are processed transiently and excluded from KAORI storage, notifications, and audit metadata. Do not claim the process never receives plaintext.

## Destructive operations

ConfigMap and Secret deletion use:

```text
Live target selection
Best-effort impact review
Exact-name confirmation
Non-destructive validation receipt
Final destructive confirmation modal
Server-side resourceVersion recheck
Deletion
```

The modal is the final human confirmation. It does not replace the signed receipt, RBAC preflight, or resourceVersion precondition. ConfigMap and signed Secret delete receipts are stateless, bound to the KAORI user and exact live target plus resourceVersion, and expire after ten minutes.

## Protected Secret Reveal

Protected Reveal uses Tab Style 3:

```text
New Request | My Requests | Approvals
```

Only the active registry panel polls. The one-time value uses Protected Value Panel and is removed on timeout, visibility loss, navigation, or HTMX replacement.

## Pagination

Reveal registries and bulk TLS target tables use scoped HTMX pagination with explicit endpoint, query parameters, target, and owning loading state. Numeric pages must not navigate to a partial endpoint as a full page.


## Bulk TLS Rotation layout

Bulk TLS Rotation presents certificate and private-key upload as two peer main-content cards. A compact file-processing boundary follows them. The five-step Controlled TLS Rotation Flow is rendered full width after upload and target selection through the shared `workflow_control()` primitive. Validation/update actions are embedded in the same control section rather than separated into a side panel.

Single TLS rotation also uses a full-width workspace. `Target TLS Secret` is a compact identity-first section: Cluster, Namespace, and Secret form one three-column strip; Current TLS Posture follows with a four-metric grid and a separate Issuer/Fingerprint row so long technical values have enough width. The retired target/posture split must not return. `Replacement Certificate Pair & Validation` combines the peer `tls.crt` / `tls.key` upload cards, guardrails, validation result, and an embedded canonical action bar. `Controlled Rotation & Governance Posture` renders `components/operational_point_flow.html` full-width and follows it with one compact horizontal Governance evidence strip; the retired large side panel and sticky right-side controlled-flow/posture rail must not return.

TLS file chooser controls must use an explicit `type="button"` trigger plus a `hidden` native file input. Do not wrap the upload card in a `<label>` with an `sr-only` file input: browser focus restoration after the native file dialog can move the viewport and make the sticky rail appear to jump. After selection, focus returns to the visible chooser with `preventScroll: true`; the selected filename is announced through `aria-live="polite"`.


## ConfigMap validation evidence

Create, Update, and Delete display a persistent validation preview inside the primary workspace. The preview has only three states: `Pending`, `Validated`, and `Failed`. Changing a target, entry, update mode, immutable setting, or exact-name confirmation invalidates the prior state. Update validation shows added, changed, removed, and unchanged keys without exposing value content.

Create and Update use one server-side dry-run for a validation request. A final mutation request performs one fresh server-side dry-run and then exactly one mutation. Delete validation does not send DELETE; it rereads the live object, evaluates effective delete authorization, and issues a signed resource-version receipt.

## Operational toast

Operational results use `components/operational_toast.html` and `#operational-toast-stack`. The toast and Activity Audit record originate from the same normalized event. The stack is limited to four visible items. Success, information, and warning results auto-dismiss; errors persist. Hover and keyboard focus pause auto-dismiss. Legacy quick-action toast templates, close handlers, and domain feedback wrappers are not retained.


## Form + Right Context Reference v1

**Canonical component:** `components/form_with_context_rail.html`  
**Visual references:** Add Kubernetes Connection, Register Prometheus Connection, Register Alertmanager Connection, and Create Kubernetes ConfigMap.

Browser review established the Integration registration composition as a reusable KAORI layout family rather than a provider-specific implementation detail. The pattern is now formally named **Form + Right Context** and is available to any focused create, edit, register, or configuration task whose main form should remain dominant while workflow/safety/reference guidance remains secondary.

Create ConfigMap established the cross-domain reference; Update/Delete ConfigMap, Create/Replace/Delete Secret, and Protected Reveal New Request now consume the same shared component. The Integration registration pages retain their existing copied geometry until the Integrations final recheck; during that review they should migrate to the shared component without changing appearance or interaction behavior.

Canonical composition:

```text
form layout
→ form_context.layout_classes()
→ 12-column desktop grid

primary form card
→ form_context.main_classes()
→ 8/12 columns
→ one outer card
→ identity / payload / validation as internal sections
→ embedded final action bar

guidance column
→ form_context.rail_classes()
→ 4/12 columns
→ sticky top-5
→ Info Flow
→ Information Guide / Related Page / Context Guidance as needed
```

Reviewed ConfigMap CRUD and Secret CRUD use `data-kubernetes-operation-layout="form-context-v1"` and consume the shared Form + Right Context geometry. Protected Reveal uses the same geometry only inside the `New Request` tab; `My Requests` and `Approvals` remain full-width registry views. New reviewed consumers must not copy `xl:grid-cols-12`, `xl:col-span-8`, or `xl:col-span-4` bundles directly. TLS rotation retains its dedicated reviewed full-width composition.

See `docs/design/components/FORM_WITH_CONTEXT_RAIL.md`.

### Responsive rule

The Form + Right Context pattern stacks the guidance below the primary form below `xl`. This preserves the same semantic order used by existing Kubernetes, Prometheus, and Alertmanager registration pages. Do not create a provider- or domain-specific breakpoint solely to keep the rail visible.

