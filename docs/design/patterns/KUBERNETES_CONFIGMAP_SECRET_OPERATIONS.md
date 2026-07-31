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
- mutation remains validation-gated, but the server always revalidates;
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

The modal is the final human confirmation. It does not replace the signed receipt, RBAC preflight, or resourceVersion precondition.

## Protected Secret Reveal

Protected Reveal uses Tab Style 2:

```text
New Request | My Requests | Approvals
```

Only the active registry panel polls. The one-time value uses Protected Value Panel and is removed on timeout, visibility loss, navigation, or HTMX replacement.

## Pagination

Reveal registries and bulk TLS target tables use scoped HTMX pagination with explicit endpoint, query parameters, target, and owning loading state. Numeric pages must not navigate to a partial endpoint as a full page.


## Bulk TLS Rotation layout

Bulk TLS Rotation presents certificate and private-key upload as two peer main-content cards. A compact file-processing boundary follows them. The five-step Controlled TLS Rotation Flow is rendered full width beneath the upload cards through `components/operational_flow_steps.html`, using arrows rather than a tall side column. Validation actions remain in the canonical Form Action Bar beneath the flow.
