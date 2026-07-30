# KAORI Styling Guide

Status: Canonical implementation guide
Applies to: All authenticated KAORI pages, reusable Jinja components, HTMX partials, drawers, modals, forms, tables, reports workspaces, and operational states.

## 1. Purpose

This guide is the practical entry point for building and reviewing KAORI pages. It translates the global design system into reusable implementation decisions so page styling does not depend on repeated visual correction.

The detailed visual contract remains in `KAORI_DESIGN_SYSTEM.md` and the component documents under `docs/design/components/`. This guide does not replace those contracts; it tells implementers which shared component to use and where a page-local implementation is prohibited.

## 2. Non-Negotiable DRY Contract

1. Use an existing shared component before writing page-local utility bundles.
2. Change shared geometry, typography, radius, or interaction in the owning component first.
3. Do not copy a shared component's Tailwind classes into a page template.
4. Do not create a new component based only on a visual variation. A component must represent a reusable semantic purpose.
5. Domain templates own content, routes, data, authorization, and HTMX parameters. Shared components own recurring presentation.
6. No template-local `<style>` blocks or raw hex colors.
7. Avoid inline JavaScript and event handlers. Existing debt is bounded and reduced page by page.
8. Do not introduce arbitrary font sizes or radii when an approved role exists.
9. Every page review must reduce or preserve the style-drift baseline; it must never increase it.

Run the guardrails:

```bash
python scripts/verify_ui_reuse.py
python scripts/verify_ui_style.py
```

When a reviewed page removes existing style drift, regenerate the per-file ceiling in the same change:

```bash
python scripts/verify_ui_style.py --write-baseline
```

Review the baseline diff before committing. A lower count is expected; moving debt to another template is not.

## 3. Documentation and Component Authority

| Concern | Source of truth | Shared implementation |
|---|---|---|
| Global color, shape, spacing, interaction | `KAORI_DESIGN_SYSTEM.md` | `frontend/styles.css` tokens |
| Hero | `components/HERO.md` | `components/page_hero.html` |
| Typography | `components/TYPOGRAPHY.md` | Owning shared component classes |
| Tables and labels | `components/TABLE_AND_LABEL.md` | `components/table.html`, `components/table_label.html` |
| Pagination | `components/PAGINATION.md` | `components/pagination.html` |
| Tab style registry | `components/TAB_STYLES.md` | Approved semantic tab components |
| Tab Style 1 — Integrated Workspace Tabs | `components/WORKSPACE_TABS.md` | `components/workspace_tabs.html` |
| Tab Style 2 — Compact Segmented Tabs | `components/SEGMENTED_TABS.md` | `components/segmented_tabs.html` |
| Visualization Workspace Style 1 | `components/VISUALIZATION_WORKSPACE.md` | `components/visualization_workspace.html` |
| Topology visualization palette | `components/TOPOLOGY_PALETTE.md` | `frontend/styles.css` tokens |
| Operational section card | `components/OPERATIONAL_SECTION_CARD.md` | `components/operational_section_card.html` |
| Snapshot context bar | `components/SNAPSHOT_CONTEXT_BAR.md` | `components/snapshot_context_bar.html` |
| Inventory asset card | `components/INVENTORY_ASSET_CARD.md` | `components/inventory_asset_card.html` |
| Right-side detail drawer | `components/SIDE_DRAWER.md` | `components/side_drawer.html` |
| Operational callout | `components/OPERATIONAL_CALLOUT.md` | `components/operational_callout.html` |
| Forecast projection chart | `components/FORECAST_PROJECTION_CHART.md` | `components/forecast_projection_chart.html` |
| Compact section-header action | `components/SECTION_HEADER_ACTION.md` | `components/section_link_button.html` |
| Right contextual rail | `components/RIGHT_CONTEXT_RAIL.md` | `components/context_rail.html` |
| Primary flow box | `components/INFO_FLOW.md` | `components/info_flow.html` |
| Operational flow steps | `components/OPERATIONAL_FLOW_STEPS.md` | `components/operational_flow_steps.html` |
| Related workspace box | `components/RELATED_PAGE_CARD.md` | `components/related_page_card.html` |
| Expandable supporting content | `components/VIEW_MORE_CONTENT.md` | `components/view_more_content.html` and wrappers |
| Form actions | `components/FORM_ACTION_BAR.md`, `components/BUTTON.md` | `components/form_action_bar.html`, `components/action_button.html` |
| Empty/error/loading | component-specific contracts | `components/states/`, `components/loading_bar.html` |

A page-specific requirement may select and compose these components but may not override their standard geometry.

## 4. Color Palette and Semantic Use

### Brand palette

- Primary Bright Violet: `#7C3AED`
- Primary Hover: `#6D28D9`
- Primary Dark: `#5B21B6`
- Accent Lavender: `#A78BFA`
- Primary Soft: `#EDE9FE`

Templates use semantic tokens such as:

- `bg-kaori-primary`
- `bg-kaori-soft`
- `text-kaori-primary`
- `bg-surface-card`
- `text-content-primary`
- `border-outline-default`

Do not use raw palette utilities such as `bg-violet-600`, `text-gray-500`, or literal hex values in page templates.

### Operational semantics

| Meaning | Family |
|---|---|
| Healthy, Ready, Connected, Active | Normal / green |
| Information, Pending, Processing | Info / blue |
| Degraded, Warning, Maintenance, Partial | Warning / amber |
| Failed, Critical, Blocked, Destructive | Critical / red |
| Unknown, Disabled, Not Configured | Neutral / slate |

Violet communicates KAORI identity, selection, focus, contextual metadata, and primary actions. It does not replace operational status colors.

## 5. Font Hierarchy

The hierarchy is semantic. Implementers do not choose a size based on available space or personal preference.

| Role | Standard | Casing |
|---|---|---|
| Hero title | Owned exclusively by `page_hero.title_classes()` | Title Case |
| Major page title outside hero | `text-2xl font-semibold` | Title Case |
| Section title | `text-lg font-semibold` | Title Case |
| Card/table-block title | `text-base font-semibold` | Title Case |
| Subsection/expandable title | `text-sm font-semibold` | Title Case |
| Primary resource identity | `text-sm font-semibold` | Preserve source casing |
| Body/input value | `text-sm font-normal` | Sentence/source case |
| Description/helper text | `text-xs` or shared `text-sm` contract | Sentence case |
| Table header/form label | `text-xs font-semibold` | Title Case |
| Compact status/metadata label | `text-[10px] font-semibold`, shared component only | Short canonical text |

Rules:

- Use `font-semibold` as the default heading weight.
- Ordinary titles use `text-content-primary`, not Violet.
- Description text must remain visually subordinate to its title.
- Do not add `text-[13px]`, `text-[15px]`, or other arbitrary sizes in page templates. Existing approved arbitrary values live inside shared components only.
- Technical identifiers preserve their exact casing. Do not apply mechanical Title Case to Kubernetes names, profile keys, URLs, hashes, or API versions.
- Visible headings, tabs, filter labels, table headers, and action labels use Title Case. Narrative descriptions use sentence case.

## 6. Hero Standard

Every authenticated page that uses a hero imports:

```jinja
{% import "components/page_hero.html" as page_hero %}
```

The shared hero owns:

- outer height, radius, padding, and 7/5 desktop grid;
- eyebrow, title, and description typography;
- metadata labels;
- right-side context panel;
- hero action geometry and states.

Required content hierarchy:

```text
Identity → Purpose → Context → Action
```

Hero limits:

- one eyebrow;
- one authoritative `h1`;
- one concise description, normally one or two lines;
- two or three metadata labels;
- no more than two normal actions;
- one optional right context panel with exactly two compact metrics and one bottom action.

Do not place tables, charts, workflow instructions, diagnostic evidence, or paragraph-length copy in the hero. Do not change hero font size or height per page.

## 7. Label Standard

`components/table_label.html` is the canonical compact label implementation.

### Standard status label

Use `table_label.status_label(...)`.

- semantic soft background following status;
- semantic text color;
- no border;
- `rounded-md`, never pill-shaped;
- minimum height 24 px;
- 10 px semibold text;
- concise wording;
- no decorative icon.

Use `table_label.status_indicator_label(...)` when a small semantic dot improves scanning. The label remains borderless.

### Metadata label

Use `table_label.metadata_label(...)`.

- borderless Violet-soft contextual treatment;
- used for category, type, scope, count, or identity metadata;
- optional contextual icon when it adds meaning;
- never used for health or failure state.

### Special label

Use `table_label.special_label(...)` only when a compact label requires both stronger separation and an explicit icon, for example:

- hero posture or eligibility;
- gated readiness requiring attention;
- a compact destructive or security boundary;
- a special state whose icon materially improves recognition.

Special labels may use a semantic border and icon. This is an explicit exception, not the default status treatment. Do not recreate special label classes inline.

### Label decision

```text
Operational state? → status_label
Operational state needing a scan dot? → status_indicator_label
Context/category/type/count? → metadata_label
Exceptional compact state needing icon + border? → special_label
Ordinary value? → plain text
```

## 8. Radius and Surface Standard

| Element | Radius |
|---|---|
| Main shell, hero, large grouped surface, primary Info Flow, Related Page Card | `rounded-2xl` / 16 px |
| Standard card, dropdown, expandable content | `rounded-xl` / 12 px |
| Page-level button, form input/select, navigation row, ordinary icon surface | `rounded-lg` / 8 px |
| Compact table filter, table action, pagination control, status/metadata label | `rounded-md` / 6 px |
| Avatar, status dot, toggle, progress track, ordered step marker | `rounded-full` only when the circular shape has semantic purpose |

Do not use `rounded-3xl` or arbitrary radii in authenticated workspaces.

Standard surfaces use semantic tokens and restrained shadows. Nested cards should rely on border, surface contrast, and whitespace before adding another shadow.

## 9. Pagination Standard

Every server-paginated table uses `components/pagination.html` and the global pagination contract.

- default page size: 5;
- allowed page sizes: 5, 10, 25, 50;
- numeric page-size selector;
- resource-aware result summary on the left;
- Previous, numeric pages, and Next grouped on the right;
- active page uses Violet Soft;
- disabled Previous/Next renders as a non-interactive element with `aria-disabled="true"`;
- page-size, filter, and sorting changes reset to page 1;
- HTMX updates only the owning table/workspace region and preserves filters and sort state.

Do not create custom Previous/Next geometry or page counters per page.

### Dashboard table pagination

Operational dashboard tables follow the same contract. Page-size changes reset to page 1, preserve the active scope, and update only the owning section through HTMX. Enabled navigation uses `pagination.navigation_classes()`; disabled navigation is a non-interactive element using `pagination.navigation_classes(disabled=true)`.

## 10. Tab Style 1 — Integrated Workspace Tabs

Use **Tab Style 1** (`integrated-workspace`) through `components/workspace_tabs.html` for peer sections inside one operational workspace. Tabs are navigation, not a large card that wraps every panel. The complete multi-style registry lives in `components/TAB_STYLES.md`.

Required behavior:

- the tab bar attaches to the workspace through a simple bottom divider;
- it does not render its own rounded card, background, border shell, or shadow;
- each tab has `role="tab"`, `aria-controls`, selected state, and keyboard focus treatment;
- each panel has the matching `role="tabpanel"` and `aria-labelledby`;
- the active tab is stored in the URL, for example `?tab=capacity`;
- HTMX scope or filter changes preserve the active tab;
- page-local `role="tablist"` geometry is prohibited when the shared component can represent the workspace.

Tabs switch peer content. They do not hide blockers, required form fields, errors, or a primary flow. New tab styles require a distinct information architecture, a semantic key, one shared component owner, and registration in `TAB_STYLES.md`; visual variation alone is insufficient.

### Tab Style 2 — Compact Segmented Tabs

Use `components/segmented_tabs.html` (`compact-segmented`) for two or three local mutually exclusive views inside one component, inspector, drawer, or visualization toolbar. It is not a top-level workspace navigation style. The owning controller provides Left/Right/Home/End keyboard behavior and may persist the selected view in the URL when sharing or refresh continuity is useful.

### Visualization Workspace Style 1 — Adaptive Explorer

Use `components/visualization_workspace.html` (`adaptive-explorer`) for dense interactive visualizations. At very wide breakpoints it may expose persistent Controls, Canvas, and Inspector panes. On normal laptops the canvas remains primary while Controls and Details become adaptive drawers. A fixed `context_rail` is not an inspector substitute.

Visualization workspaces must provide a keyboard-accessible textual representation when graph interaction is not equivalent for keyboard and screen-reader users. Renderer failure preserves the committed data through that textual view. Raw visualization colors belong in tokenized CSS variables, never page templates or JavaScript.

## 11. Right-Side Context Boxes

Use the shared layout:

```jinja
{% import "components/context_rail.html" as context_rail %}
```

The desktop rail is 20rem wide, stacks below the main workspace on smaller screens, and uses 16 px vertical spacing between boxes.

Choose a box by purpose:

- **Info Flow** — a primary three-to-five-step ordered process.
- **Related Page Card** — one related KAORI destination with one action.
- **Information Guide Card** — expandable non-sequential reference content.
- **Context Guidance Card** — expandable secondary ordered guidance.
- **Page Context Card** — static context or authority boundary.
- **Workspace Summary Card** — compact peer-workspace summary.
- **Semantic readiness block** — blocking or operational state, not generic guidance.

Do not create a custom right-side box because of a different color, icon, or local content length. Extend the semantic component only when the new need is reusable across modules.

Preferred rail order:

```text
Primary Flow or Readiness
Related Workspace
Supporting Information
```

## 12. View More Content

Secondary expandable content uses `components/view_more_content.html` through a semantic wrapper.

Default affordance:

- closed: `View Details`;
- open: `Collapse`.

Use a more specific label when useful, such as `View Evidence` or `View Sections`. Avoid vague `View More` copy.

Expandable content is allowed for secondary guidance and reference detail. It is not allowed for:

- required form fields;
- blockers or readiness requirements;
- primary request preview;
- critical errors;
- destructive consequences;
- primary operational flows.

Primary ordered workflows continue to use Info Flow.

## 13. Table Standard

Every operational table uses `components/table.html` and `components/table_label.html`.

Required block order:

```text
Block Header
Loading Bar
Filters
Table Header and Rows
Empty/Error State
Pagination Footer
```

Core rules:

- default left alignment;
- final action column right aligned;
- 14 px primary table content;
- 12 px supporting context;
- 12 px semibold column headers in Title Case;
- no more than two preferred visible row actions;
- default page size 5;
- filter controls 40 px high with compact `rounded-md` geometry;
- table rows use subtle dividers and Violet-mist hover;
- long details move to expandable row, drawer, modal, or detail page.

Do not wrap every value in a badge. Plain operational data remains plain text.

### Compact cluster inventory table

Use the compact cluster inventory pattern when the table compares fleet scope rather than every asset count inline. The canonical columns are:

```text
Cluster | Connection | Total Objects | Last Snapshot | Inventory Signals | Details
```

- The final column contains one compact `View Details` button.
- Asset counts move into the shared right-side drawer.
- The drawer preserves table context and contains identity, asset breakdown, snapshot context, and signals.
- Normal freshness is not repeated as an Inventory Signal. Signals represent conditions requiring awareness.
- Pagination uses resource-aware Title Case, for example `Showing 1–3 of 3 Clusters`, plus a visible `Rows` label.

## 14. Forms and Actions

Use:

- `components/action_button.html` for standard primary/secondary action geometry;
- `components/form_action_bar.html` for the stable helper-and-actions footer.

Rules:

- exactly one visually dominant primary action per group;
- primary action uses solid KAORI Violet;
- destructive action uses Critical semantic color;
- visible action labels use Title Case and describe the result;
- controls are 40 px high with `rounded-lg`;
- icon precedes text;
- secondary action appears before primary action;
- disabled/loading states preserve geometry.

Avoid ambiguous labels such as `Submit` or `Confirm` when `Create Report Request`, `Save Configuration`, or `Run Validation` is clearer.

## 15. Cards, Information Blocks, and Readiness

A standard content card contains:

- optional 36–40 px icon surface;
- 16 px semibold Title Case title;
- 12–14 px sentence-case description;
- one clear content purpose;
- no more than two header actions.

Readiness and status blocks use semantic state, not Violet decoration. A blocking requirement remains visible and is never hidden inside expandable content.

Avoid stacking multiple dark or tinted backgrounds. Use whitespace, divider, border, and hierarchy before adding another nested surface.

### Snapshot context bar

Use `snapshot_context_bar.html` for committed, archived, or worker-generated datasets. It owns the semantic snapshot state, concise interpretation, source strip, latest collected time, active scope, committed coverage, and snapshot exceptions. The canonical compact layout uses a 4/8 composition, inline source metadata, and four neutral context metrics in one desktop row. Exact sync time, freshness, and coverage belong here and must not be repeated in the hero.

### Inventory asset card

Use `inventory_asset_card.html` for one navigable Kubernetes asset type. Asset cards show count, title, concise purpose, and `Open Inventory`. They are destination cards, not operational status cards.

### Right-side detail drawer

Use `side_drawer.html` when row details are too large for an expanded row but the comparison table must remain visible. The shared drawer owns overlay, panel geometry, close behavior, scrolling, accessibility, optional footer action, and reusable `section(...)` and `metric(...)` content primitives. Rich operational drawers follow Summary → Identity/Snapshot → Domain Breakdown → Signals → Operational Context. Drawer and section descriptions stay concise; self-explanatory identity/context sections may omit descriptions. Summary values use a divided plain-metric row instead of nested metric cards when card-inside-card density would dominate. The final Operational Context remains visible, states the data boundary, and gives one state-aware next action.

### Operational section card

Repeated dashboard blocks use `components/operational_section_card.html`. The shared component owns the shell, header spacing, 40 px icon surface, `text-base font-semibold` title, supporting description, optional compact badge, and one optional section-header action. Domain templates own the data and body content through `caller()`.

### Operational callout

Use `components/operational_callout.html` for reusable explanatory or semantic cards inside an operational section. Neutral callouts use an elevated surface with a semantic icon tile. Semantic callouts may use a matching semantic border and surface because they are interpretation cards, not compact labels. Page templates must not copy the semantic class bundle inline.

Do not copy the standard `rounded-xl border bg-surface-card shadow-sm` section shell into every dashboard partial. Do not wrap a tab workspace in another card when each section already has its own surface.

When two dashboard blocks are both primary content, use `components/peer_content_grid.html`. Use an equal 6/6 split or the documented 7/5 split. Both peer sections use `h-full`, and asynchronous wrappers use `h-full w-full`, so the shorter card stretches to the tallest box in the row. Do not force a peer chart, readiness summary, or operational guidance block into the fixed 20rem context rail.

### Dashboard metric typography

| Metric role | Standard |
|---|---|
| Primary KPI value | `text-2xl font-semibold` |
| Secondary summary value | `text-xl font-semibold` |
| Compact metric value | `text-base font-semibold` |
| Row or table value | `text-sm font-semibold` |
| Axis and chart microcopy | Owned by the shared chart component |

Ordinary dashboard cards do not introduce `text-3xl` or arbitrary sizes.

### Compact section-header action

`components/section_link_button.html` is the approved 36 px action exception for a card header. It uses `h-9`, `rounded-lg`, and `text-xs font-semibold`. A section header may contain at most one such action. Normal page and form actions remain 40 px.

### Forecast projection chart

Historical and projected utilization visuals use `components/forecast_projection_chart.html`. The component owns gridlines, thresholds, historical/forecast line semantics, axis microcopy, legend, and approved arbitrary chart typography. Dashboard and Analytics templates provide the series and horizon; they do not copy SVG geometry.

### Primary and secondary flows

`components/info_flow.html` is static and always visible. It is reserved for a page-level primary ordered process that users must understand to complete or operate the page. The legacy `open_by_default` argument remains accepted only for call-site compatibility and has no visual effect.

When an action, response, or validation sequence is one of two peer main-content boxes, use `components/operational_flow_steps.html`. The flow is static, uses visible step boxes, and stretches with its peer card. This pattern applies to capacity action, alert response, reporting, and equivalent operational sequences.

`components/context_guidance_card.html` remains expandable only for optional secondary guidance in a genuine supporting rail. Do not use it for peer main content and do not duplicate the same sequence in multiple components.

## 16. Workspace Catalog and Landing Pages

Role-aware landing catalogs use the pattern documented in `patterns/WELCOME_WORKSPACE_CATALOG.md`.

Required rules:

- keep the canonical hero unchanged;
- use a section-level catalog title rather than a second page title;
- show access scope and visible result count as inline metadata, not a separate tinted summary box;
- use the standard 40 px search control;
- use `workspace_link_card.html` for a card whose complete purpose is opening one peer workspace;
- use `table_label.metadata_label(...)` for scope, category, and type;
- do not use pill labels, hover translation, heavy floating shadows, or decorative elements without semantic purpose;
- use the shared empty-state component when search returns no authorized destination;
- keep search limited to server-authorized cards already rendered for the user.

Welcome may use `welcome_capability_group.html` as a documented dark Violet category anchor. This is a landing-page orientation pattern, not a second hero and not a general content-card variant.

## 17. Loading, Empty, Error, and Permission States

- Loading appears in the affected region, never by replacing the hero.
- Initial dashboard sections use local skeletons; paginated or filterable dashboard tables also own a loading bar inside their section header.
- `hx-indicator` always points to the bar owned by the same partial region; a global dashboard loading bar is prohibited.
- Dashboard initial loads use section-owned skeleton placeholders. A global loading bar must not represent several unrelated asynchronous dashboard sections.
- Empty states explain what is absent and the next valid action when one exists.
- Error copy is concise; technical evidence belongs in detail views, toast, or Activity Audit Log.
- Unknown, unavailable, permission denied, and not configured are separate states.
- Permission-restricted actions follow the authorization contract and must not look like temporary loading.

## 18. Responsive, Dark Mode, and Accessibility

Every reusable component is reviewed in:

- light and dark mode;
- 1366×768, 1440×900, and 1920×1080;
- open and closed navigation shell;
- loading, empty, error, disabled, unknown, and permission states;
- keyboard navigation and visible focus.

Responsive reflow preserves semantic order. Primary content appears before contextual rail content. Icon-only actions require accessible names. Status never relies on color alone.

## 19. Page Review Workflow

Review one main page at a time using this sequence:

1. Identify the page's hero type and replace any local hero shell.
2. Map every title and description to the approved font hierarchy.
3. Replace custom status/category badges with shared label macros.
4. Normalize card and control radii.
5. Replace custom right-side layout and boxes with `context_rail` and semantic components.
6. Replace custom expandable sections with View More Content or Info Flow according to purpose.
7. Replace table, filter, action, and pagination geometry with shared components.
8. Remove duplicate instructions and repeated context.
9. Validate HTMX targets so hero and stable headers do not re-render.
10. Run style and contract guardrails.
11. Update the style baseline only when the reviewed page's counts decrease.
12. Record any genuinely new reusable pattern in this guide and its own component contract before using it elsewhere.

## 20. Pull Request Checklist

- [ ] Existing shared components were reused.
- [ ] No copied hero, pagination, table, label, or right-rail classes were introduced.
- [ ] Font roles match the hierarchy.
- [ ] Standard labels are semantic, borderless, and rectangular.
- [ ] Icon + border labels use the explicit special-label exception.
- [ ] Hero geometry and content limits are unchanged.
- [ ] Pagination defaults to 5 with 5/10/25/50 options.
- [ ] Workspace tabs use the shared component and preserve URL/HTMX state.
- [ ] Local two/three-view switches use Tab Style 2 rather than page-local segmented geometry.
- [ ] Dense visualization pages use the Adaptive Explorer owner and provide an accessible Resource List fallback.
- [ ] Visualization colors come from documented CSS tokens; templates and JavaScript contain no raw palette values.
- [ ] Repeated operational sections use `operational_section_card.html`.
- [ ] Forecast charts use the shared projection chart.
- [ ] Right-side boxes use the semantic component decision table.
- [ ] Required content is not hidden inside expandable sections.
- [ ] No raw hex, page-local CSS, or new inline script/event debt was added.
- [ ] Light/dark, responsive, loading, empty, error, disabled, and permission states were reviewed.
- [ ] `verify_ui_reuse.py`, `verify_ui_style.py`, and relevant contract tests pass.

## 16. Inventory Resource Page Pattern

Use `patterns/INVENTORY_RESOURCE_PAGE.md` for per-asset inventory pages such as Nodes, Namespaces, Workloads, Pods, Services, Ingresses, Storage, and Configuration.

Canonical order:

```text
Hero → Snapshot Context → Resource Posture → Filtered Table → Inline Detail
```

The hero owns identity, active scope, and high-level health. Snapshot time and coverage belong only to the Snapshot Context Bar. Capacity and resource-specific signals belong to a shared Resource Posture section.

### Detail Style 1 — Inline Expanded Detail

Use semantic key `inline-expanded` for dense row-owned details. The shared expandable row and detail primitives own loading, geometry, typography, and the open/close action. The detail must finish with a visible committed-data boundary and state-aware operational guidance.

### Technical values

Use `components/technical_value.html` for IP addresses, UUIDs, versions, runtime identifiers, kernel versions, architecture, and similar machine-oriented values. These values use normal proportional detail typography by default. Reserve `monospace=true` for raw-copy identifiers, hashes, commands, and code-like values where exact character alignment is useful. Do not represent ordinary technical values as labels.


## 21. Namespace Inventory and Technical Metadata

Namespace Inventory follows `patterns/KUBERNETES_NAMESPACE_INVENTORY.md` and is the second canonical Inventory Resource Page implementation. The hero owns lifecycle posture, the Snapshot Context Bar owns collection context, and `resource_posture_grid.html` owns factual control coverage.

`Terminating` is an informational lifecycle transition unless KAORI has duration, finalizer, or explicit policy evidence that the transition is stuck. Missing ResourceQuota, LimitRange, NetworkPolicy, or PSA labels remain neutral evidence until evaluated against an explicit governance policy. Do not infer compliance failure from absence alone.

Dense labels, annotations, selectors, and key/value metadata use `components/technical_metadata_collection.html`. Do not render large chip clouds or page-local metadata grids. The component owns entry count, wrapping, scrolling, empty evidence, and optional context.

## 22. Workload Inventory and Related Resources

Workload Inventory follows `patterns/KUBERNETES_WORKLOAD_INVENTORY.md` and is the third canonical Inventory Resource Page implementation.

Workload resources have heterogeneous factual states. Templates must separate semantic operational posture (`Stable`, `Progressing`, `Failed`, `Suspended`, `Unknown`) from type-specific evidence such as replica readiness, Job completion, or CronJob schedule state.

Update strategy, restart policy, DNS policy, pull policy, selectors, tolerations, and other workload configuration remain factual evidence until an explicit KAORI governance policy evaluates them. Do not assign warning or success colors based only on a configuration choice.

Use `components/related_resource_collection.html` for peer related resources such as Workload Pods. Do not represent peer resources as a timeline. The component owns identity, supporting evidence, semantic status, truncation context, empty evidence, and the optional destination action.

## 23. Adaptive Detail Density and Page-Size Ownership

Dense Inline Expanded Detail pages may use **Adaptive Detail Stacks** when evidence cards have different natural lengths. Namespace and Workload Inventory are the canonical references.

Required rules:

- use two independent vertical stacks with natural-height cards;
- use `detail.detail_card(..., stretch=false, density='compact')` for compact evidence cards;
- use `detail.evidence_grid(...)` for factual metrics and controller evidence;
- do not force unrelated cards to the height of the longest card;
- equal-height remains required only for true peer main-content boxes where side-by-side comparison is the purpose;
- do not add fixed `min-height` values to hide content imbalance.

Inventory page-size controls must refresh the owning `*-inventory-scope` with `outerHTML`, not only the table body. This keeps the filter form's hidden `per_page` value synchronized. Filter forms listen to their own bubbled `change` events and scoped search input events; do not use a global `change from:select` trigger that can capture the separate Rows selector.

## 21. Pod Runtime and Container Evidence

Pod Inventory follows `patterns/KUBERNETES_POD_INVENTORY.md`.

- Separate semantic operational state from Kubernetes phase and readiness evidence.
- Use Ready, Starting, Not Ready, Failed, Completed, and Unknown for Pod posture.
- Running is not equivalent to Ready; every regular container must be Ready.
- Succeeded is Completed, not a currently running healthy Pod.
- Restart counts are cumulative factual values unless a time-windowed signal exists.
- Use `container_runtime_collection.html` for regular, init, and ephemeral container runtime rows.
- A terminated init container with exit code `0` is Completed; non-zero termination is Failed.
- Related Resource Collection may omit status for ConfigMap, Secret, and PVC references.
- QoS, restart policy, DNS policy, host network, security-context presence, pull policy, selectors, and tolerations remain neutral factual evidence until an explicit governance policy evaluates them.
- Pod Rows selectors refresh the owning inventory scope, matching Node, Namespace, and Workload page-size ownership.
