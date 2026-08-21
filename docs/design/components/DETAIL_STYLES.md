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
- desktop Inventory width is bounded by `92rem` and available viewport space;
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
- Node Inventory declares `data-kaori-inventory-detail="v9"` with an editorial technical inspector; remaining Kubernetes Inventory details retain the V6 contract until migrated;
- resource headers use `detail.workspace_header(...)` instead of hand-authored heading/font classes;
- the resource title is rendered through `detail.inventory_title(...)` inside `detail.header_identity_row()` so title, metadata, and primary state form one scan line.

### Typography hierarchy

Inventory View Details uses one predictable scale across Node, Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration:

```text
Resource title       text-xl / semibold
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
Resource Profile Workspace
Relationships and Technical Metadata
Committed Snapshot Boundary
State-Aware Guidance
Optional Related Operation
```

## Resource Profile Layout

Use the resource profile layout when evidence groups have materially different content lengths.

- mark Inventory implementations with `data-kaori-detail-density="resource-profile"`;
- use independent vertical stacks rather than one equal-height row;
- use natural-height cards with `stretch=false`;
- use asymmetric splits when one evidence domain needs more width;
- Kubernetes Inventory uses `detail.inventory_section(...)` for natural-height evidence groups;
- use `detail.inventory_row(...)`, `detail.inventory_technical_row(...)`, and `detail.inventory_fact_grid(...)` for aligned factual evidence;
- Inventory field values are left-aligned in a consistent second column to avoid large eye-travel across wide modal cards;
- grouped fact grids use one shared boundary with internal separators instead of one rounded tile per value;
- keep large tables, relationships, metadata, and Operational Context full width;
- do not add fixed or minimum heights to mask content imbalance.

Resource profile layout is the canonical Kubernetes Inventory presentation inside Full Workspace Modal.

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

### Inventory Resource Profile (V5)

Kubernetes Inventory details use a contained resource-profile layout built for operational scanning.

- The modal is intentionally narrower than the viewport (`78rem` maximum) so field labels and values remain readable and eye travel stays bounded.
- The modal uses content-driven height up to the viewport limit; short resources do not look artificially empty while long resources scroll inside the workspace.
- Evidence domains use one natural-height card each. Do not create one card per metric or one borderless wall of rows.
- Two independent vertical stacks are preferred for the primary evidence area so a taller Identity card does not create empty space beneath a shorter Capacity card.
- Field labels and values share the same `text-sm` body scale. Labels are secondary/regular; values are primary/medium.
- Summary values use `text-base`; the resource title uses `text-xl`; supporting guidance stays `text-xs`.
- Large metadata and key collections use one contained list surface with row dividers. Key-heavy resources may scroll inside the collection rather than extending the entire modal indefinitely.
- KAORI violet is reserved for icons and selected emphasis. Factual surfaces remain neutral; semantic colors are used only for state.
- Repeated committed-snapshot boundary copy should not be duplicated inside every resource section when the modal footer already establishes that boundary.


## Kubernetes Inventory Horizontal Section Stack V6

Inventory View Details uses full-width horizontal section bands. Each band owns one evidence domain: a restrained Violet identity rail on the left and factual evidence on the right. Desktop layouts do not place peer evidence cards side by side, so unequal content height never creates visual misalignment. Metadata/count tags use the canonical KAORI Violet label treatment; semantic states remain green/amber/red. Field labels and factual values share the same body scale; hierarchy is created with tone and weight rather than arbitrary font-size jumps.


## Node Inventory Editorial Technical Inspector V9

Node Inventory uses an editorial technical inspector inside Full Workspace Modal. The layout removes the duplicate left rail and allocates width from the expected length and semantics of each value.

- the header owns Node name, Cluster, Role, and primary readiness; the body does not need a second identity rail;
- the summary is an integrated four-segment ribbon rather than four floating cards;
- Identity & Snapshot is a full-width fact group, while Capacity and Network Identity use a `4/12` and `8/12` split so hostname/FQDN values do not feel cramped;
- Runtime & Platform is one full-width section with separate Host Platform and Kubernetes Runtime columns;
- Scheduling & Conditions uses five lightweight semantic state facts in one row on wide screens, keeping short values visually compact;
- System UUID, IP addresses, hostname/FQDN, architecture, kernel version, runtime identifier, Kubernetes versions, and taints use selective monospace at the standard body scale; human-readable values stay in Inter;
- predictable long values stay on one line on desktop and use localized horizontal overflow only when necessary;
- Node Labels use stacked key/value pairs. Keys use a compact monospace treatment, values remain prominent, and two-column layout preserves long label names without awkward label/value wrapping;
- Committed Snapshot and state-aware operational guidance use asymmetric `5/12` and `7/12` widths so the longer operational message receives more room.

Node V9 remains Node-specific while it is validated against real cluster data. Other Kubernetes Inventory resources continue to use the V6 horizontal section stack.
