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

- Kubernetes Inventory uses `resource_detail_modal.inventory_host(...)` for one shared modal contract;
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
- resource title, metadata, and primary lifecycle/readiness/collection state use the shared `detail.header_identity_row()` owner as one grouped identity row;
- the supporting description renders below that identity row; do not float the primary state onto a second badge line or detach it beneath the leading icon/modal outer edge;
- the summary uses the shared `data-resource-detail-summary` owner;
- Kubernetes Inventory detail roots declare `data-kaori-inventory-detail="v2"`;
- resource headers use `detail.workspace_header(...)` instead of hand-authored heading/font classes;
- the resource title is rendered through `detail.inventory_title(...)` inside `detail.header_identity_row()` so title, metadata, and primary state form one scan line.

### Typography hierarchy

Inventory View Details uses one predictable scale across Node, Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration:

```text
Resource title       text-lg / semibold
Summary value        text-base / semibold
Section/card title   text-sm / semibold
Field label          text-sm / medium / secondary
Field value          text-sm / medium / primary
Supporting copy      text-xs / regular / muted
```

Technical identifiers use the same `text-sm / medium` body value scale through `technical_value.render(..., size='body')`. Inventory field labels and factual values intentionally share the same 14px body scale; hierarchy comes from tone and weight, not arbitrary font-size jumps. Supporting copy alone steps down to `text-xs`. Do not create smaller monospace or arbitrary-size value typography inside Inventory details. Metadata pair collections follow the same secondary-label / primary-value hierarchy.

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
- Kubernetes Inventory uses `detail.inventory_section(...)` for natural-height evidence groups;
- use `detail.inventory_row(...)`, `detail.inventory_technical_row(...)`, and `detail.inventory_fact_grid(...)` for aligned factual evidence;
- Inventory field values are left-aligned in a consistent second column to avoid large eye-travel across wide modal cards;
- grouped fact grids use one shared boundary with internal separators instead of one rounded tile per value;
- keep large tables, relationships, metadata, and Operational Context full width;
- do not add fixed or minimum heights to mask content imbalance.

Adaptive stacks are valid inside Full Workspace Modal and compact inline details.

### Inventory evidence surface rules

The Inventory modal is an evidence workspace, not a card gallery. Keep the visual hierarchy restrained:

```text
Header identity row
Summary strip
Two-column natural-height evidence sections
Full-width relationships / large collections
Operational boundary and next action
```

Use one section boundary per evidence domain. Do not wrap every metric in a standalone rounded card. Large key inventories use the grouped shared collection surface so dozens of keys remain scannable without producing a wall of floating tiles. Identity labels and factual values share the same `text-sm` body scale. Labels use medium secondary text, values use medium primary text, section titles use semibold, and only supporting copy steps down to `text-xs`.
