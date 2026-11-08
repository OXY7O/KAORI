# Loading Standard

KAORI uses the **Activity Audit Table** as the reference loading pattern for operational blocks.

The loading bar belongs **inside the owning header**, directly below the title/action row and before filters, summaries, forms, or data. It must not float over content or sit at the bottom of a card.

## Dashboard section loading

Read-only dashboards combine section skeletons with section-owned loading bars:

- Initial asynchronous dashboard sections render the shared skeleton placeholder inside the exact section that will be replaced.
- A table or block with pagination, filters, or in-place refresh also renders its own loading bar inside its header.
- `hx-indicator` points only to the loading bar owned by the same partial region.
- The current table content remains visible during pagination or filter requests until the replacement response arrives.
- Do not place one global loading bar in a summary card and use it as the indicator for unrelated sections.

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
- Initial loading placeholders may render the same bar as active while also showing section-local skeleton content.
- HTMX-only states use `htmx-indicator` and an explicit `hx-indicator` selector.
- HTMX replaces only the relevant region; the loading bar must not shift the hero or unrelated content.
- Real execution progress bars are separate from loading indicators and may be determinate or indeterminate based on worker progress evidence.
- Under `prefers-reduced-motion: reduce`, the shared indeterminate loading segment expands to a stable full-width Violet state and pulse/spin animation is suppressed. Loading visibility and `aria` semantics remain unchanged.

This contract applies to Cluster Health Summary, Jobs & Executions, Endpoint & Access, Compatibility & Capability Matrix, Runtime Health & Diagnostics, Recent Runtime Observations, and equivalent operational blocks.
