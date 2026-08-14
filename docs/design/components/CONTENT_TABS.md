# KAORI Content Tabs

## Purpose

Content Tabs are the canonical compact tab treatment for switching several closely related views inside one already-established workspace surface. They are visually denser than Integrated Workspace Tabs and do not create a second parent workspace hierarchy.

## Registry

- Review label: **Tab Style 4 — Content Tabs**
- Semantic key: `content-tabs`
- Component owner: `app/templates/components/content_tabs.html`
- Primary references: Kubernetes Analytics Overview, Utilization, Capacity, Workload, Storage, Forecast, and Top Consumers.

## When to Use

Use Content Tabs when all views:

- share one page, scope, and analysis context;
- are subordinate to an existing workspace heading;
- benefit from compact pill-like navigation;
- may have four or more peer content views;
- do not require the stronger page-level hierarchy of Integrated or Framed Workspace Tabs.

Do not use Content Tabs for a security-sensitive multi-step peer workspace such as Protected Secret Reveal, for a full Integration parent workspace, or for a two-view local visualization toggle.

## Geometry

The shared component owns:

- compact `min-h-10` tab controls;
- icon + label composition;
- optional compact user-facing metadata badge;
- active KAORI Violet treatment;
- neutral inactive treatment;
- wrapping by default;
- optional single-row `nowrap` mode with horizontal overflow as the narrow-viewport fallback.

A dense Overview may use `nowrap=true` only when the labels have already been shortened to concise user-facing vocabulary. Horizontal overflow is the fallback, not a reason to expose internal identifiers or abbreviate labels into unclear acronyms.

## Badge Contract

A badge is optional and must be actual user-facing metadata such as a compact count or posture label.

Never pass an internal section key, snapshot key, DOM target, dataset identifier, or loader mode as a visible badge. Consumers with richer internal tuples must call the component with `show_badges=false` or provide a dedicated display tuple.

## Runtime Ownership

The component owns active/inactive visual class tokens. A page controller owns state and applies the class contract exposed by each rendered tab through:

- `data-kaori-tab-active-classes`;
- `data-kaori-tab-inactive-classes`.

Controllers must not duplicate Tailwind palette/state class lists.

Kubernetes Analytics uses `app/static/js/analytics/kubernetes/controls.js` as its single tab-state owner. Analytics templates must not add a parallel Alpine `activeTab` controller for the same tabset.

The Analytics controller owns:

- click activation;
- Arrow Left/Right, Home, and End keyboard navigation;
- `aria-selected` and roving `tabindex`;
- native `hidden` state for panels;
- optional URL/session persistence;
- one-time lazy HTMX activation through `kaori:analytics-tab-activated`.

## Progressive Fallback

The server must render one valid active tab and panel before JavaScript executes. Non-default panels use the native `hidden` attribute. If the controller does not execute, the initial content remains readable rather than producing a blank workspace.

## Accessibility

Required semantics:

- wrapper uses `role="tablist"`;
- controls use `role="tab"`;
- each tab has `aria-controls`;
- active tab has `aria-selected="true"` and `tabindex="0"`;
- inactive tabs have `aria-selected="false"` and `tabindex="-1"`;
- panels use `role="tabpanel"` and `aria-labelledby`;
- decorative icons are `aria-hidden="true"`.

## Analytics Overview Reference

The reviewed Overview vocabulary is:

`Usage · Capacity · Workload · Storage · Consumers · Forecast · Alerts · Actions · Guidance`

Internal identifiers such as `resource-snapshot`, `capacity-snapshot`, or `top-consumers` are runtime metadata and must never be rendered beside those labels.

## Review Checklist

- Uses `components/content_tabs.html` directly.
- No domain compatibility wrapper exists.
- One state owner only.
- Shared component owns active/inactive visual classes.
- Internal identifiers are not visible badges.
- Initial panel is server-readable without JavaScript.
- Keyboard and ARIA contracts are intact.
- Dense one-row mode remains readable at the 14-inch target viewport and scrolls rather than wraps on narrower viewports.
