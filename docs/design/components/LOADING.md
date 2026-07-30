# Loading Standard

KAORI uses the **Activity Audit Table** as the reference loading pattern for operational blocks.

The loading bar belongs **inside the owning header**, directly below the title/action row and before filters, summaries, forms, or data. It must not float over content or sit at the bottom of a card.

## Dashboard section loading

Read-only dashboards use a different loading treatment from mutable operational tables:

- Initial asynchronous dashboard sections render the shared skeleton placeholder inside the exact section that will be replaced.
- The current dashboard content remains visible during in-place pagination or scope refresh until the replacement response arrives.
- Do not place one global loading bar in a summary card and use it as the indicator for unrelated sections.
- A table-specific loading bar remains valid only when it is owned by that table block and sits inside its header.

Canonical structure:

```html
<header class="border-b ... px-5 py-4">
  <div class="...title and actions...">...</div>
  <div class="htmx-indicator mt-4 h-1 overflow-hidden rounded-full bg-kaori-soft">
    <div class="h-full w-1/3 animate-pulse rounded-full bg-kaori-primary"></div>
  </div>
</header>
```

Rules:

- The track is `h-1`, rounded, Violet Soft, and constrained by the header padding.
- The visible segment is one-third width, KAORI Violet, rounded, and pulse-animated.
- Worker-active states may render the same bar as `block`; HTMX-only states use `htmx-indicator`.
- `hx-indicator` must point to the loading bar owned by the same partial region.
- HTMX replaces only the relevant region; the loading bar must not shift the hero or unrelated content.
- Real execution progress bars are separate from loading indicators and may be determinate or indeterminate based on worker progress evidence.

This contract applies to Jobs & Executions, Endpoint & Access, Compatibility & Capability Matrix, Runtime Health & Diagnostics, Recent Runtime Observations, and equivalent operational blocks.
