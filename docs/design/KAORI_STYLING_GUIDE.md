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
| Right contextual rail | `components/RIGHT_CONTEXT_RAIL.md` | `components/context_rail.html` |
| Primary flow box | `components/INFO_FLOW.md` | `components/info_flow.html` |
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

## 10. Right-Side Context Boxes

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

## 11. View More Content

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

## 12. Table Standard

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

## 13. Forms and Actions

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

## 14. Cards, Information Blocks, and Readiness

A standard content card contains:

- optional 36–40 px icon surface;
- 16 px semibold Title Case title;
- 12–14 px sentence-case description;
- one clear content purpose;
- no more than two header actions.

Readiness and status blocks use semantic state, not Violet decoration. A blocking requirement remains visible and is never hidden inside expandable content.

Avoid stacking multiple dark or tinted backgrounds. Use whitespace, divider, border, and hierarchy before adding another nested surface.

## 15. Loading, Empty, Error, and Permission States

- Loading appears in the affected region, never by replacing the hero.
- Empty states explain what is absent and the next valid action when one exists.
- Error copy is concise; technical evidence belongs in detail views, toast, or Activity Audit Log.
- Unknown, unavailable, permission denied, and not configured are separate states.
- Permission-restricted actions follow the authorization contract and must not look like temporary loading.

## 16. Responsive, Dark Mode, and Accessibility

Every reusable component is reviewed in:

- light and dark mode;
- 1366×768, 1440×900, and 1920×1080;
- open and closed navigation shell;
- loading, empty, error, disabled, unknown, and permission states;
- keyboard navigation and visible focus.

Responsive reflow preserves semantic order. Primary content appears before contextual rail content. Icon-only actions require accessible names. Status never relies on color alone.

## 17. Page Review Workflow

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

## 18. Pull Request Checklist

- [ ] Existing shared components were reused.
- [ ] No copied hero, pagination, table, label, or right-rail classes were introduced.
- [ ] Font roles match the hierarchy.
- [ ] Standard labels are semantic, borderless, and rectangular.
- [ ] Icon + border labels use the explicit special-label exception.
- [ ] Hero geometry and content limits are unchanged.
- [ ] Pagination defaults to 5 with 5/10/25/50 options.
- [ ] Right-side boxes use the semantic component decision table.
- [ ] Required content is not hidden inside expandable sections.
- [ ] No raw hex, page-local CSS, or new inline script/event debt was added.
- [ ] Light/dark, responsive, loading, empty, error, disabled, and permission states were reviewed.
- [ ] `verify_ui_reuse.py`, `verify_ui_style.py`, and relevant contract tests pass.
