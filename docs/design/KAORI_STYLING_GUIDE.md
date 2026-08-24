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
| Tab Style 2 — Framed Workspace Tabs | `components/FRAMED_WORKSPACE_TABS.md` | `components/framed_workspace_tabs.html` |
| Tab Style 3 — Compact Segmented Tabs | `components/SEGMENTED_TABS.md` | `components/segmented_tabs.html` |
| Visualization Workspace Style 1 | `components/VISUALIZATION_WORKSPACE.md` | `components/visualization_workspace.html` |
| Topology visualization palette | `components/TOPOLOGY_PALETTE.md` | `frontend/styles.css` tokens |
| Operational section card | `components/OPERATIONAL_SECTION_CARD.md` | `components/operational_section_card.html` |
| Snapshot context bar | `components/SNAPSHOT_CONTEXT_BAR.md` | `components/snapshot_context_bar.html` |
| Inventory asset card | `components/INVENTORY_ASSET_CARD.md` | `components/inventory_asset_card.html` |
| Right-side detail drawer | `components/SIDE_DRAWER.md` | `components/side_drawer.html` |
| Operational callout | `components/OPERATIONAL_CALLOUT.md` | `components/operational_callout.html` |
| Forecast projection chart | `components/FORECAST_PROJECTION_CHART.md` | `components/forecast_projection_chart.html` |
| Analytics Overview surface hierarchy | `components/ANALYTICS_ANALYSIS_SURFACES.md` | `analytics/components/_analysis_surfaces.html` |
| Analytics Capacity Analysis | `components/ANALYTICS_CAPACITY_ANALYSIS.md` | Capacity templates + shared analytics surfaces |
| Analytics Storage Analysis | `components/ANALYTICS_STORAGE_ANALYSIS.md` | Storage templates + shared evidence record components |
| Analytics Workload Analysis | `components/ANALYTICS_WORKLOAD_ANALYSIS.md` | Workload templates + shared analysis, evidence, and filter components |
| Analytics Alerts & Anomalies | `components/ANALYTICS_ALERTS_ANOMALIES.md` | Alerts templates + shared analysis, evidence, and pagination components |
| Compact section-header action | `components/SECTION_HEADER_ACTION.md` | `components/section_link_button.html` |
| Right contextual rail | `components/RIGHT_CONTEXT_RAIL.md` | `components/context_rail.html` |
| Primary flow box | `components/INFO_FLOW.md` | `components/info_flow.html` |
| Operational flow steps | `components/OPERATIONAL_FLOW_STEPS.md` | `components/operational_flow_steps.html` |
| Related workspace box | `components/RELATED_PAGE_CARD.md` | `components/related_page_card.html` |
| Expandable supporting content | `components/VIEW_MORE_CONTENT.md` | `components/view_more_content.html` and wrappers |
| Form actions | `components/FORM_ACTION_BAR.md`, `components/BUTTON.md` | `components/form_action_bar.html`, `components/action_button.html` |
| Empty / blocked / error / loading | `components/EMPTY_ERROR_STATE.md`, `components/empty-state.md` | `components/states/_empty_state.html`, `components/states/_blocked_state.html`, `components/loading_bar.html` |

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

Hero copy budget:

- description target: 7–12 words, hard maximum 16 words;
- right-panel title: 2–4 words;
- status label: 1–3 words;
- metric label: 1–3 words;
- metric helper: optional, maximum 4 words.

Inventory and operations context metrics normally include a concise helper of one to four words when it improves interpretation. Use label + value only when the metric is fully self-explanatory. Snapshot boundaries, diagnostic explanations, and longer interpretation belong below the hero.

Hero limits:

- one eyebrow;
- one authoritative `h1`;
- one concise description, normally one or two lines;
- two or three metadata labels;
- no more than two normal actions;
- one optional right context panel with exactly two compact metrics and one full-width primary action.

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

### Analytics Analysis Surface Hierarchy and Snapshot Standard

Capacity is the reference composition for Analytics pages and Analytics Overview. Utilization, Capacity, Workloads, Storage, Consumers, Forecast, Alerts, Action Summary, and Recommendations use one shared visual grammar while preserving domain-appropriate evidence layouts:

1. one calm snapshot shell;
2. one compact header with icon, semantic posture, description, and at most one drill-down action;
3. one peer metric strip when the domain has summary metrics;
4. one neutral evidence or context body with compact role-colored anchors;
5. one neutral interpretation, decision, or recommended-action region using the shared Brand, Insight, Evidence, or Status role.

Primary evidence, analytical context, interpretation, recommended action, review path, and execution guidance use neutral surfaces with subtle outlines or separators. Color is concentrated in compact icon tiles, eyebrow labels, badges, charts, and bars. Dataset Attention uses a neutral strip plus one semantic Warning glyph and compact badge.

Do not tint the entire Metrics Source/readiness body, chart, record list, metric card, or guidance region. Use `analytics/components/_analysis_surfaces.html`; individual tabs must not reconstruct the snapshot shell, header, metric geometry, role icon geometry, guidance composition, or surface hierarchy.

Analytics assigns color by visual role: Brand Violet for identity/navigation/actions, Insight cyan for explanation/methodology, Evidence slate for passive context, and semantic green/amber/red/slate only for actual operational state. Status tones are normalized through `table_label.semantic_tone(...)`. Critical, Warning, and Normal values must never fall back to the Unknown/slate treatment.

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

### Tab Style 2 — Framed Workspace Tabs

Use `components/framed_workspace_tabs.html` (`framed-workspace-v2`) for peer operational domains inside one explicit parent workspace surface. The shared component owns the raised connected tabs, optional semantic badges, ARIA linkage, and keyboard hooks. The owning controller stores the active tab in the URL and synchronizes browser history.

### Tab Style 3 — Compact Segmented Tabs

Use `components/segmented_tabs.html` (`compact-segmented`) for two or three local mutually exclusive views inside one component, inspector, drawer, or visualization toolbar. It is not a top-level workspace navigation style. The owning controller provides Left/Right/Home/End keyboard behavior and may persist the selected view in the URL when sharing or refresh continuity is useful.

### Visualization Workspace Style 1 — Adaptive Explorer

Use `components/visualization_workspace.html` (`adaptive-explorer`) for dense interactive visualizations. At very wide breakpoints it may expose persistent Controls, Canvas, and Inspector panes. On normal laptops the canvas remains primary while Controls and Details become adaptive drawers. A fixed `context_rail` is not an inspector substitute.

Visualization workspaces must provide a keyboard-accessible textual representation when graph interaction is not equivalent for keyboard and screen-reader users. Renderer failure preserves the committed data through that textual view. Raw visualization colors belong in tokenized CSS variables, never page templates or JavaScript.

## 11. Right-Side Context Boxes

Use the shared layout:

```jinja
{% import "components/context_rail.html" as context_rail %}
```

The default desktop rail is 20rem wide. Dense live-mutation workspaces may use the shared `wide` variant at 22rem so operational flow and guidance copy remain readable. Both variants stack below the main workspace on smaller screens and use 16 px vertical spacing between boxes.

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
- table/registry zero states use `components/states/_empty_state.html` rather than page-local icon/title/description blocks;
- filtered zero results use the semantic label `No Results`; healthy operational zero states use factual domain wording;
- unavailable prerequisites use the blocked-state component, with `blocked_state_variant='table'` inside a table body;
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

Use `snapshot_context_bar.html` for committed, archived, or worker-generated datasets. It owns the semantic snapshot state, concise interpretation, source strip, latest collected time, active scope, committed coverage, and snapshot exceptions. The canonical compact layout uses a 4/8 composition, inline source metadata, and four transparent neutral metrics in one desktop row separated by subtle dividers. Do not place each metric in a Lavender/Violet tile. Semantic color is limited to the status label and meaningful coverage/exception icons. Exact sync time, freshness, and coverage belong here and must not be repeated in the hero.

### Inventory asset card

Use `inventory_asset_card.html` for one navigable Kubernetes asset type. Asset cards show count, title, concise purpose, and `Open Inventory`. They are destination cards, not operational status cards.

### Right-side detail drawer

Use `side_drawer.html` for compact contextual summaries that benefit from keeping the comparison table visible, such as Inventory Overview cluster details. The shared drawer owns overlay, panel geometry, close behavior, scrolling, accessibility, optional footer action, and reusable `section(...)` and `metric(...)` content primitives. Rich operational drawers follow Summary → Identity/Snapshot → Domain Breakdown → Signals → Operational Context. Drawer and section descriptions stay concise; self-explanatory identity/context sections may omit descriptions. Summary values use a divided plain-metric row instead of nested metric cards when card-inside-card density would dominate. The final Operational Context remains visible, states the data boundary, and gives one state-aware next action. Long values inside narrow drawer identity or snapshot columns use `details/_detail_content.html::stacked_detail_row(...)` so labels and values wrap within their owning column instead of forcing horizontal overflow. Canonical short metadata such as `Snapshot Source: Committed Snapshot` remains a horizontal `detail_row(..., nowrap=True)`.

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

Canonical owners are `docs/design/components/EMPTY_ERROR_STATE.md` and `docs/design/components/empty-state.md`.

- Loading appears in the affected region, never by replacing the hero.
- Initial dashboard sections use local skeletons; paginated or filterable dashboard tables also own a loading bar inside their section header.
- `hx-indicator` points to the bar owned by the same partial region.
- Dashboard initial loads use section-owned skeleton placeholders. A page-level bar must not represent unrelated asynchronous dashboard sections.
- Analytics Overview may add one compact composite progress strip because all tracked lazy requests belong to the same Overview workspace and progress is calculated from explicit section states. Local skeletons and the filter-owned loading bar remain required.
- Full table, registry, workspace, and major-card empty states use `components/states/_empty_state.html`; reviewed pages do not duplicate the icon/title/description geometry locally.
- `No Results` means active search/filter state returned zero rows. Initial setup, uncollected snapshots, and healthy zero-result states use wording that states the actual condition.
- Unavailable dependencies and unmet prerequisites use `components/states/_blocked_state.html`; table-body blockers use `blocked_state_variant='table'`.
- Empty or blocked states remain inside the same owning HTMX region so refresh, filters, and pagination do not change geometry.
- HTMX out-of-band fragments are response-only helpers and must not appear as ordinary inline content during the initial full-page render.
- Error copy is concise; technical evidence belongs in detail views, toast, or Activity Audit Log.
- Unknown, unavailable, permission denied, and not configured are separate states.
- Permission-restricted actions follow the authorization contract and must not look like temporary loading.

## 18. Responsive, Dark Mode, and Accessibility

Every reusable component is reviewed in light and dark mode, at supported desktop widths, and with keyboard focus.

Dark mode must follow `components/DARK_MODE.md`:

- use the semantic `page → shell → card → elevated` surface stack;
- keep ordinary content neutral;
- reserve Bright Violet for focus, primary interaction, selection, and compact identity accents;
- use the canonical Hero-owned gradient only through `page_hero.html`;
- do not introduce page-local `dark:bg-slate-*`, raw dark hex values, or duplicate module token sets;
- preserve status semantics, contrast, loading, empty, error, disabled, and permission states.

Review at 1366×768, 1440×900, and 1920×1080 at 100% zoom. Verify expanded/collapsed sidebar, Hero, cards, tables, forms, dropdowns, dialogs, and drawers.

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
- [ ] Framed multi-domain workspaces use Tab Style 2; local two/three-view switches use Tab Style 3 rather than page-local segmented geometry.
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
Hero → Snapshot Context → Resource Posture → Filtered Table → Full Workspace Modal
```

The hero owns identity, active scope, and high-level health. Snapshot time and coverage belong only to the Snapshot Context Bar. Capacity and resource-specific signals belong to a shared Resource Posture section.

### Detail Style 2 — Full Workspace Modal

Use semantic key `full-workspace-modal` for Node through Configuration Inventory. `components/resource_detail_modal.html` owns near-fullscreen geometry, loading, URL state, focus management, and close behavior. Server-rendered detail content supplies the resource header, summary, evidence, relationships, metadata, committed-data boundary, and state-aware guidance.

`Detail Style 1 — Inline Expanded Detail` remains available only for short row-owned evidence that does not justify a dedicated workspace.

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

Full Workspace Modal content may use **Adaptive Detail Stacks** when evidence cards have different natural lengths. Namespace and Workload Inventory are the canonical references.

Required rules:

- use two independent vertical stacks with natural-height cards;
- use `detail.detail_card(..., stretch=false, density='compact')` for compact evidence cards;
- use `detail.evidence_grid(...)` for factual metrics and controller evidence;
- do not force unrelated cards to the height of the longest card;
- equal-height remains required only for true peer main-content boxes where side-by-side comparison is the purpose;
- do not add fixed `min-height` values to hide content imbalance.

Inventory scope-changing filters must refresh the owning `*-page-workspace` with `outerHTML` so Hero context, snapshot evidence, summary posture, dependent options, and rows remain synchronized. Page-size and pagination controls refresh only `*-table-content` with `innerHTML`; their requests carry the active filters and `partial_mode=table_content`. Do not retain `*-inventory-scope` wrapper partials after a page adopts the canonical workspace contract. Filter forms listen to their own bubbled `change` events and scoped search input events; do not use a global `change from:select` trigger that can capture the separate Rows selector.

Canonical filtered tables also expose **Clear Filters** only when at least one user filter/search value differs from its default. Clear resets the filtered result to page 1, preserves the selected Rows/per-page value, refreshes the same owning HTMX region with the same loading indicator, and removes filter query state from the pushed URL where that registry owns URL state. Use `components/table_registry.html`; do not introduce `Reset Filter` / `Reset Filters` page-local variants.

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

## 24. Service and Ingress Network Inventory

Service and Ingress Inventory follow `patterns/KUBERNETES_NETWORK_INVENTORY.md`.

- Service table: `Service | Scope | Access Model | Port Mapping | Backend Registration | Details`.
- Ingress table: `Ingress | Scope | Publication | TLS References | Routing | Details`.
- NodePort and LoadBalancer are publication configuration, not proof of public exposure.
- Service traffic policies, IP-family policy, session affinity, and publish-not-ready configuration remain factual until evaluated by an explicit governance policy.
- Service backend evidence is collected from EndpointSlice first, with Endpoints fallback for compatibility.
- A selector-based Service with zero reported addresses is `No Registered Backends`, not `Ready`.
- Ingress class and path type are metadata, not health status.
- No TLS reference remains neutral inventory evidence; a TLS Secret reference does not validate certificate existence, expiry, or hostname coverage.
- Ingress backend Services are resolved against the current committed Service Inventory only.
- Declared hosts are shown as technical values. Opening a declared host is an explicit user action and does not imply reachability.

### Detail evidence density

`detail.evidence_grid(...)` owns compact factual evidence tiles. It must not expose empty grid-background cells when the final row is incomplete. Technical Metadata Collection avoids nested vertical scrolling inside expanded details; large collections may use later progressive-disclosure patterns, but not a fixed internal scrollbar by default. Key-only inventories use the shared 12 px supporting-text token. Narrow pair collections such as Tolerations use the shared compact-pair layout so the key column does not force the value into an unreadable strip.

Use body-size proportional Technical Value presentation for technical values inside ordinary table cells. Compact Technical Value remains appropriate in detail rows and supporting metadata.

## 25. Storage and Configuration Inventory

Storage and Configuration Inventory follow the canonical Inventory Resource Page pattern.

Storage uses `Storage Object | Scope | Provisioning | Capacity & Access | Binding & Lifecycle | Details`. StorageClass is factual provisioning configuration and uses `Configured`, not a synthetic Kubernetes health state. Reclaim policy, access modes, provisioner name, binding mode, expansion, and topology configuration remain factual until an explicit governance policy evaluates them. PV/PVC lifecycle may use semantic status because Bound, Pending, Released, Failed, and Lost are operational lifecycle evidence.

Configuration uses `Configuration Object | Scope | Object Type | Metadata & Mutation | Current References | Details`. ConfigMap and Secret are metadata labels, not status. Immutable and Mutable are factual mutation models. Configuration Inventory uses key-index collection: key names may be indexed, but value content is not decoded, logged, persisted, or displayed. Collection capability states are stored on the committed cluster generation and may be `Collected`, `Permission Unavailable`, `API Unavailable`, or `Adapter Not Selected`.

Use `technical_metadata_collection.html` with `mode='keys'` for key-name inventories and `mode='records'` for condition evidence. Related claims, mounted Pods, and current Pod references use `related_resource_collection.html`.

## 26. Inventory Detail Workspace and View Details

Node, Namespace, Workload, Pod, Service, Ingress, Storage, and Configuration Inventory use **Detail Style 2 — Full Workspace Modal**.

Shared owners:

- `components/resource_detail_modal.html`
- `components/details/_detail_content.html`
- `app/static/js/detail_rows.js`

The table action remains `View Details`, but it opens a maximized modal workspace instead of inserting an expanded row. The modal preserves table height, current filters, pagination, Rows, and background scroll position.

Required behavior:

- near-fullscreen viewport geometry with a `100rem` desktop maximum;
- fixed resource header, summary strip, and footer;
- independently scrollable evidence body;
- `?detail=<id>` URL state;
- Back closes and Forward reopens the detail;
- deep-link reload can fetch a detail outside the visible page;
- focus trap, Escape close, backdrop close, and focus restoration;
- modal-owned loading and error states;
- fetched detail roots use `data-kaori-detail-variant="full-workspace-modal"`;
- resource headers use `data-resource-detail-header`;
- summary regions use `data-resource-detail-summary`.

Inventory Overview keeps the right-side drawer because it is a compact cluster summary. Topology keeps the Adaptive Explorer Inspector because selection is graph-owned.

Do not create page-local Inventory modals, dense expanded rows, or alternate `View More` geometry.

## 27. Kubernetes Live Mutation Workspaces

ConfigMap and Secret operations follow `patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md`.

### Operational workflow catalog

Use `components/operational_workflow_catalog.html` for the shared catalog shell and `components/operational_workflow_card.html` for operation destination rows. The canonical presentation is one bordered catalog surface containing natural-height rows separated by subtle dividers; do not render a grid of floating cards or nested boundary boxes. Permission is always represented as `Available` or `Restricted`; `Standard`, `Controlled`, `Protected`, and `Destructive` are separate operation classifications.

### Live Mutation Evidence Contract

Place `components/operation_evidence_boundary.html` directly below the Hero to distinguish:

```text
Live Target     → Kubernetes API
Impact Context  → Committed Inventory
Outcome Record  → Activity Audit
```

Do not describe Inventory-backed references as complete or live impact analysis.

### Mutation workspace

Use a compact Hero, Evidence Boundary, primary form with `context_rail.html`, server validation evidence, and `form_action_bar.html`. Form labels use 12 px semibold typography; normal controls use a 40 px minimum height and 14 px values.

Use `components/structured_entry_editor.html` for repeatable ConfigMap and Secret entries. Use `components/choice_card_group.html` for form choices that change the input schema.

### Sensitive values

Use the phrase `No KAORI Value Persistence`. Values may be processed transiently, but they must not be persisted in KAORI data models, job payloads, notifications, or Activity Audit metadata.

Protected one-time values use `components/protected_value_panel.html`. They clear on expiry, visibility loss, navigation, or HTMX replacement and do not expose a default Copy action.

### Destructive confirmation

ConfigMap and Secret Delete require the canonical final destructive confirmation modal after validation. The modal does not replace exact-name confirmation, signed validation receipts, RBAC preflight, final target reread, or resourceVersion preconditions.

### Protected Reveal

Use Tab Style 4 — Content Tabs for `New Request`, `My Requests`, and `Approvals`, matching the reviewed Kubernetes Analytics compact treatment. Protected Reveal uses the controlled progressive-link mode so each tab retains a real server-navigation fallback while Alpine owns instant switching, URL state, and keyboard movement. Only the active registry panel may poll. Numeric pagination owns its endpoint, filters, HTMX target, and loading boundary.

### Inventory modal technical text

Full Workspace Modal uses a maximum width of `100rem`, hides horizontal page overflow, and wraps resource titles, relation identities, labels, annotations, hosts, selector keys, and multi-line technical values. Technical Metadata Collection reserves a readable key column and uses `overflow-wrap:anywhere`; it must not truncate evidence or create nested vertical scrolling.


### Dark appearance interaction guardrail

Shared secondary and validation actions use a neutral default surface, then solid KAORI Violet with white text on hover and Deep Violet on active. Hero context badges use an opaque white surface because ordinary dark-page semantic soft colors do not provide reliable contrast on the Violet Hero panel. Secret Type selection uses the native checked radio as the only visual authority; exactly one card receives the selected border, surface, icon, and `Selected` indicator.

Delete action fragments marked for HTMX out-of-band replacement must only render in HTMX responses. Full-page GET rendering must never place an action fragment above the operation workspace.

## 28. TLS Certificate Governance Registry

TLS Certificate Governance follows `patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md` and is the canonical Governance Resource Registry reference.

Canonical order:

```text
Hero → Collection Snapshot → Governance Posture → Compact Registry → Full Workspace Modal
```

- validity uses `Valid`, `Renewal Window`, `Critical Window`, `Expired`, `Invalid`, and `Unknown`;
- expiry is based on the exact certificate timestamp, not floored integer days;
- current default policy is a 30-day Renewal Window and 7-day Critical Window, exposed through configuration;
- host coverage uses `Fully Covered`, `Partial`, `Uncovered`, `No Declared Hosts`, or `Not Reported`;
- declared-host coverage is not live reachability evidence;
- Secret collection and Ingress mapping maintain separate collection evidence;
- Governance owns view and sync; Kubernetes Secret Operations owns rotation;
- the collector deliberately accesses only `tls.crt`; private-key and unrelated Secret values must not be accessed or persisted;
- table Details opens the shared Full Workspace Modal directly; no intermediate expanded row is used;
- Rows refreshes the owning TLS inventory scope and all numeric pagination links preserve active filters.

### Compact operation destinations

Operational Workflow Catalog actions use naturally sized secondary buttons. Do not use large solid-Violet blocks for every destination. The catalog row itself owns destination grouping; action controls must not create an additional nested card surface.

### Operational Point Flow

Use `components/operational_point_flow.html` for concise supporting sequences. For Bulk TLS Rotation, the flow is expandable and closed by default. It contains numbered points only; required upload fields, validation feedback, and mutation actions remain outside the expandable content.




### Analytics Metrics Source Readiness Standard

All Metrics Source-backed Kubernetes Analytics pages use the canonical analytics readiness surfaces and `analytics/kubernetes/components/_metrics_source_status.html`. The card always displays the canonical semantic state, response latency, and provider `last_checked_at`. Dataset generation time, worker-attempt time, and page-render time must never be substituted for Metrics Source Checked At. Metrics Source readiness and committed snapshot readiness remain separate peer evidence cards. Alerts & Anomalies retains Alert Source Readiness because it can resolve Alertmanager or Metrics Source dynamically.

### Resource Utilization Standard

Resource Utilization follows `components/ANALYTICS_RESOURCE_UTILIZATION.md`. Summary uses shared Resource Pressure Lanes; Trend and Node Detail load on first tab activation; hidden tabs do not poll; multi-series charts render a visible compact legend; chart JavaScript lives in a static module rather than inline Jinja.



### Analytics Storage Analysis Standard

Storage Analysis follows `components/ANALYTICS_STORAGE_ANALYSIS.md`. Top controls own Cluster and Namespace; Node is local to the Filesystem tab. Every panel states its effective scope. Filesystem, PVC, and PV record panels load on first activation, use the shared evidence-record and local-filter components, and follow the global pagination contract. Observed PVC usage must never be labeled as PV utilization or PV consumed capacity.


### Analytics Workload Analysis Standard

Workload Analysis follows `components/ANALYTICS_WORKLOAD_ANALYSIS.md`. Tenant Quota and Recommendations render with the page; Workload Resource Mapping loads on first tab activation. Summary metrics follow Cluster, Namespace, and Time Range, while local filters affect only the owning record list and filtered-count footer. Request Coverage, Limit Coverage, factual QoS metadata, and Analytics Evidence Coverage remain separate signals. Current usage must not be labeled average usage, selected-window Pod peak sums must be named as upper-bound evidence, and right-sizing requires Complete evidence. CPU limits unset are informational by default; missing memory limits remain governance warnings.

## Analytics Unavailable Metric Contract

An unavailable denominator must render `Unknown` and `N/A`, not `0.0%`. Suppress the progress bar and state how evidence can be restored. Status-bearing utilization, pressure, risk, and headroom bars use semantic color; composition, contribution, loading, and materialization bars remain KAORI Violet. Capacity Analysis is cluster-level Ready-worker fleet analysis, while node-level pressure belongs to Resource Utilization.

## Analytics Resource Forecast

Resource Forecast follows the shared Analytics Analysis Surface hierarchy and the domain contract in `components/ANALYTICS_RESOURCE_FORECAST.md`.

- Group Cluster/Namespace under Scope and Model/History/Horizon under Projection Configuration.
- Resource tabs own CPU, Memory, Storage, Pods, Trend, and Recommendations navigation. Do not duplicate this with a Resource Focus selector.
- Use neutral surfaces for forecast metrics, capacity projection, charts, resource outlook, interpretation, and recommended action.
- Use Insight cyan for methodology/How To Read and Brand Violet for What To Do or review-path anchors.
- Use Latest Daily Average, Weekly Trend, and Historical Signal Quality.
- Historical Signal Quality is not forecast accuracy.
- Unknown evidence displays N/A and suppresses progress.
- Full-page charts use the shared interactive forecast chart and canonical resource tokens.



### Analytics Alerts & Anomalies Standard

Alerts & Anomalies follows `components/ANALYTICS_ALERTS_ANOMALIES.md`. Connected source health, committed snapshot availability, anomaly collection, routing, suppression, ownership, and incident readiness remain separate evidence signals. Missing or partial evidence must not resolve to Healthy. Records, operational evidence, interpretation, attention, and recommended actions use neutral surfaces; semantic color is reserved for actual status, while Brand and Insight roles identify action and explanation. Semantic levels are normalized in the template layer and domain payloads never emit CSS classes.

## Analytics Top Consumers Standard

Use `components/ANALYTICS_TOP_CONSUMERS.md`. Top Consumers separates absolute consumption, selected-scope contribution, request utilization, limit utilization, and configuration state. All-resource sorting may use priority, contribution, namespace, or resource type, but never heterogeneous raw units. Consumer identity is structured; templates do not split display strings. Rankings use the shared ranked evidence panel, records use the shared record filter/evidence/pagination components, and contribution progress stays KAORI Violet. Namespace is a committed snapshot dimension.


### Integrations Workspace Standard

The canonical Integrations contract is documented in `components/INTEGRATIONS_WORKSPACE_STANDARD.md`; implementation history is recorded in `audits/INTEGRATIONS_FULL_AUDIT_20260731.md`.

- Primary provider, runtime, compatibility, capability, binding, and coverage evidence is bright.
- Interpretation, remediation, and destructive-boundary guidance uses the darker soft surface.
- Integrations semantic states render through the global `table_label` contract; provider pages do not own a second palette.
- Metrics Source and Alertmanager registries reuse the shared registry controls, loading, and pagination grammar while retaining provider-specific facts.
- Full-page and HTMX pagination have separate, explicit URL ownership and preserve path arguments, filters, and the active workspace tab.
- One shared runtime-history component is rendered directly; provider-local presentation wrappers are prohibited.
- Dense technical matrices may scroll only inside their owning component when simultaneous column comparison is operationally necessary.

## Intelligence Workspace Standard

- Recommendations, Rule Catalog, Alert Intelligence, and Automation Control use Inventory-aligned heroes with at most three metadata labels and two posture metrics.
- Primary collections use responsive evidence records. Technical tables are reserved for true matrix comparison.
- Rule definitions distinguish `Available`, `Imported Signal`, and `Reserved Plan`.
- A capability that is not fully connected and behavior-tested is rendered as `Reserved Plan` with disabled controls. Do not use MVP, placeholder, preview-only, or coming-soon language.
- Automation mutations are disabled by default until validation, entered-reason, confirmation, and behavior contracts are enabled.
