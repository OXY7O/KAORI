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

## Canonical mutation workspace

```text
Compact Hero
Evidence Boundary
Primary Form + Right Context Rail
Validation Evidence
Canonical Form Action Bar
```

Rules:

- primary work appears before the context rail in DOM order;
- context rail uses `components/context_rail.html` with the shared 22rem `wide` variant;
- controls use 40 px geometry and 12 px labels;
- mutation remains validation-gated, but the server always performs a fresh provider validation immediately before mutation;
- primary Info Flow remains visible; secondary summaries, policies, guardrails, and related guidance are expandable and closed by default;
- Form Action Bar remains inside the primary column and separates its title from concise helper copy;
- detailed instructions belong in Info Flow or a focused guidance card, not repeated across Hero, form, rail, and footer.

## ConfigMap entry editing

ConfigMap text and binary entries use Structured Entry Editor. Update keeps Merge and Replace explicit. Immutable ConfigMaps remain protected from update.

## Secret creation and replacement

Secret Type uses Operational Choice Card Group with responsive 1/2/3-column reflow. The selected option uses a strong Violet boundary, selected surface, check icon, and explicit `Selected` marker; changing only the rail summary is insufficient. Existing values are never rendered in Replace. Blank replacement inputs mean unchanged; submitted values mean replace.

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

Bulk TLS Rotation presents certificate and private-key upload as two peer main-content cards. A compact file-processing boundary follows them. The five-step Controlled TLS Rotation Flow is rendered full width beneath the upload cards through `components/operational_flow_steps.html`, using arrows rather than a tall side column. Validation actions remain in the canonical Form Action Bar beneath the flow.

Single TLS rotation also uses a full-width workspace. `Target TLS Secret` is a compact identity-first section: Cluster, Namespace, and Secret form one three-column strip; Current TLS Posture follows with a four-metric grid and a separate Issuer/Fingerprint row so long technical values have enough width. The retired target/posture split must not return. `Replacement Certificate Pair & Validation` combines the peer `tls.crt` / `tls.key` upload cards, guardrails, validation result, and an embedded canonical action bar. `Controlled Rotation & Governance Posture` renders `components/operational_point_flow.html` full-width and follows it with one compact horizontal Governance evidence strip; the retired large side panel and sticky right-side controlled-flow/posture rail must not return.

TLS file chooser controls must use an explicit `type="button"` trigger plus a `hidden` native file input. Do not wrap the upload card in a `<label>` with an `sr-only` file input: browser focus restoration after the native file dialog can move the viewport and make the sticky rail appear to jump. After selection, focus returns to the visible chooser with `preventScroll: true`; the selected filename is announced through `aria-live="polite"`.


## ConfigMap validation evidence

Create, Update, and Delete display a persistent validation preview inside the primary workspace. The preview has only three states: `Pending`, `Validated`, and `Failed`. Changing a target, entry, update mode, immutable setting, or exact-name confirmation invalidates the prior state. Update validation shows added, changed, removed, and unchanged keys without exposing value content.

Create and Update use one server-side dry-run for a validation request. A final mutation request performs one fresh server-side dry-run and then exactly one mutation. Delete validation does not send DELETE; it rereads the live object, evaluates effective delete authorization, and issues a signed resource-version receipt.

## Operational toast

Operational results use `components/operational_toast.html` and `#operational-toast-stack`. The toast and Activity Audit record originate from the same normalized event. The stack is limited to four visible items. Success, information, and warning results auto-dismiss; errors persist. Hover and keyboard focus pause auto-dismiss. Legacy quick-action toast templates, close handlers, and domain feedback wrappers are not retained.
