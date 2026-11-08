# Tab Style 5 — Resource Lens Tabs

- Semantic key: `resource-lens`
- Shared owner: `app/templates/components/resource_lens_tabs.html`
- Approved reference: Kubernetes Analytics → Top Consumers → CPU/Memory/Pods/PVC resource lens

## Rationale

The resource selector is a set of **four metric-rich cards that control one ranked evidence panel**, not route navigation, a two/three-option compact segmented control or another Content Tabs row. The approved DevContainer appearance is preserved. Centralize the tablist surface without re-designing the card contents or changing the data/permission boundaries.

## Requirements

- The shared `tablist()` macro must render `role="tablist"`, an accessible name and `data-kaori-tab-variant="resource-lens"`; consumers supply the four actual tab buttons and panels through the call block.
- Keep all existing `role="tab"`, `aria-controls`, `aria-selected`, roving `tabindex`, focus-visible ring, active/inactive tokens and one-to-one `tabpanel` IDs.
- Keep `data-analytics-tabset`, `data-analytics-tab-button` and `data-analytics-tab-panel` hooks and the existing keyboard controller; selection must work after HTMX refresh.
- Only the selected panel may be visible. Each resource retains its own measured unit, capacity denominator, committed snapshot authority and no additional live provider reads.
- Metric-card geometry is not a generic replacement for the canonical Content Tabs, Integrated Workspace Tabs or Compact Segmented Tabs.

## Verification before admission

Run style-verifier, full affected contract/functional tests and template lint. Verify tab clicks, Left/Right/Home/End keyboard focus, accessible names/selected states, panel switching, responsive layout and light/dark visual appearance in a real browser. DevContainer approval of the earlier UI is not equivalent to executing regression tests for this refactor.
