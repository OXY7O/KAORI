# KAORI Detail Styles

## Detail Style 1 — Inline Expanded Detail

Semantic key: `inline-expanded`

Shared owners:

- `components/details/_expandable_row.html`
- `components/details/_detail_content.html`
- `app/static/js/detail_rows.js`

Use this style only for short row-owned evidence that remains easy to scan inside the table context. It is retained for compact activity, audit, and small evidence tables.

Do not use Inline Expanded Detail for Kubernetes Inventory resources with dense identity, runtime, relationship, metadata, and operational-context sections.

## Detail Style 2 — Full Workspace Modal

Semantic key: `full-workspace-modal`

Shared owners:

- `components/resource_detail_modal.html`
- `components/details/_detail_content.html`
- `app/static/js/detail_rows.js`

Node, Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration Inventory use this style.

### Required behavior

- `View Details` opens one near-fullscreen modal without changing table height;
- desktop width is bounded by `90rem` and available viewport space;
- mobile uses the available viewport as a full workspace;
- header, summary strip, and footer remain visible while the detail body scrolls;
- Escape, backdrop, and explicit Close dismiss the modal;
- keyboard focus is trapped inside the dialog and returned to the opener;
- background workspace scrolling is locked while open;
- URL query state uses `detail=<resource-id>`;
- browser Back closes the modal and Forward reopens it;
- refresh/deep-link can load the detail even when its row is not on the current page;
- filter, page, Rows, and scroll position remain unchanged;
- loading and error states stay inside the modal;
- detail root uses `data-kaori-detail-variant="full-workspace-modal"`;
- fetched detail marks its resource header with `data-resource-detail-header`;
- lifecycle/readiness/collection state shown below a resource-header description uses the shared `detail.header_badge_row()` owner and aligns with the title/description text column after the leading icon;
- do not detach that state label as a sibling that can wrap beneath the leading icon or modal outer edge;
- the summary uses the shared `data-resource-detail-summary` owner.

### Content order

```text
Resource Header
Sticky Summary Strip
Adaptive Evidence Workspace
Relationships and Technical Metadata
Committed Snapshot Boundary
State-Aware Guidance
Optional Related Operation
```

## Adaptive Detail Stacks

Use adaptive detail stacks when evidence cards have materially different content lengths.

- mark adaptive implementations with `data-kaori-detail-density="adaptive-stacks"`;
- use independent vertical stacks rather than one equal-height row;
- use natural-height cards with `stretch=false`;
- use asymmetric splits when one evidence domain needs more width;
- use `detail.evidence_grid(...)` for compact factual evidence;
- keep large tables, relationships, metadata, and Operational Context full width;
- do not add fixed or minimum heights to mask content imbalance.

Adaptive stacks are valid inside Full Workspace Modal and compact inline details.
