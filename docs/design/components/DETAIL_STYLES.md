# KAORI Detail Styles

## Detail Style 1 — Inline Expanded Detail

Semantic key: `inline-expanded`

Shared owners:

- `components/details/_expandable_row.html`
- `components/details/_detail_content.html`

Use this style when a table row owns a dense detail view that benefits from the full table width. The Node Inventory page is the canonical reference.

### Required behavior

- one expanded row per detail group;
- compact `View Details` row action;
- on-demand detail request;
- summary first, then domain cards, metadata, and operational context;
- two columns on ordinary laptop widths and up to three columns on larger screens;
- visible data boundary and state-aware next action;
- `data-kaori-detail-variant="inline-expanded"` on the detail root.

Do not use Inline Expanded Detail for a short identity summary that fits better in the shared right-side drawer. A new detail style requires a materially different information architecture and shared owner.


Namespace Inventory is the second reference and demonstrates full-width resource controls plus Technical Metadata Collections inside the same `inline-expanded` detail style.

## Adaptive Detail Stacks

Use adaptive detail stacks when cards within one expanded detail have materially different content lengths. This is the canonical density treatment for Namespace and Workload details.

Contract:

- set `data-kaori-detail-density="adaptive-stacks"` on the detail root;
- use two independent vertical stacks rather than one equal-height grid row;
- use an asymmetric `0.82fr / 1.18fr` split when the evidence-heavy column needs more width;
- pass `stretch=false` to `detail.detail_card(...)` so each card follows its natural content height;
- reserve equal-height behavior for true peer boxes whose visual comparison benefits from matching height;
- use `detail.evidence_grid(...)` for compact numeric or factual evidence instead of long repeated label/value rows;
- keep metadata and Operational Context full-width below the primary stacks.

Do not solve uneven detail content by adding fixed or minimum heights. Do not create page-local card geometry for the same pattern.

## Inventory View Details Workspace

All Inventory implementations use the same row-owned disclosure action and expanded workspace shell.

- action labels: `View Details` / `Close Details`;
- action state: eye or close icon plus disclosure chevron;
- one open row per resource group;
- expanded row uses a subtle Violet boundary;
- loading and error content remain inside the same boundary;
- detail roots use `expanded_workspace_*_classes()` macros rather than page-local shell bundles.

This interaction supersedes legacy `View More`, `Hide Details`, and page-local expanded-row presentation.
