# KAORI Design System

This document is the authoritative global visual and interaction contract for KAORI. It defines rules that apply across modules, providers, pages, and workflows. Domain-specific page composition, table columns, metrics, actions, and provider behavior do not belong in this document.

## Documentation hierarchy

KAORI UI documentation is organized into four layers:

1. **Global Design System** — universal foundations and cross-application rules in this document.
2. **Styling Guide** — practical component selection and page-review workflow in `docs/design/KAORI_STYLING_GUIDE.md`.
3. **Component Standards** — detailed contracts for reusable components under `docs/design/components/`.
4. **Page Pattern Standards** — reusable page structures under `docs/design/patterns/`.
5. **Module UI Specifications** — domain-specific page behavior under `docs/modules/` or the owning module README.

A reference implementation demonstrates a contract; its domain-specific content is never a global rule.

### Final-recheck engineering index

The mandatory engineering and release-review source of truth is `docs/standards/KAORI_ENGINEERING_STANDARD_V1.md`. The Design System governs visual and interaction contracts; the Engineering Standard is the final-recheck index for architecture, testing, security, reliability, documentation, release governance, and CI/CD evidence.

## Design direction

The visual concept is **KAORI Violet Infrastructure**: a modern enterprise operations interface with a violet brand identity, neutral operational surfaces, restrained elevation, and conventional infrastructure status semantics.

The interface is information-first. Violet establishes KAORI identity, hierarchy, focus, and primary interaction. Health, readiness, risk, connectivity, lifecycle, and process states use semantic colors.

## Implementation contract

- Tailwind CSS v4 is the styling system.
- Design tokens are defined in `frontend/styles.css`.
- Templates use semantic utilities such as `bg-surface-card`, `text-content-primary`, and `border-outline-default`.
- Do not introduce page-specific stylesheets for ordinary layout, spacing, typography, color, radius, shadow, or interaction state.
- Do not use raw hex values in Jinja templates.
- Rebuild `app/static/css/output.css` after changing templates or tokens.
- Validate light and dark mode for every reusable component.
- Authenticated pages do not use decorative gradients. The canonical dark Hero gradient defined in `components/DARK_MODE.md` is the only approved authenticated-shell exception.
- Status must not rely on color alone; pair color with text and, when useful, an icon.
- Shared component geometry and typography are changed in the shared component first, never patched locally per page.
- The practical component-selection and page-review contract is `docs/design/KAORI_STYLING_GUIDE.md`.
- Page-local copies of hero, pagination, table, label, expandable-content, or right-context-rail utility bundles are prohibited.

The consolidated foundation and content-density decision registry is `docs/design/FOUNDATION_AND_CONTENT_DENSITY.md`. It resolves foundation-selection and density questions while this document and the owning component contracts remain the normative detailed authorities.

The consolidated responsive, accessibility, state, HTMX, overlay, and interaction registry is `docs/design/RESPONSIVE_ACCESSIBILITY_INTERACTION.md`. It selects existing shared owners and executable evidence; detailed component contracts remain normative.

## Brand palette

| Role | Light mode | Dark mode |
|---|---|---|
| Primary | `#7C3AED` | `#8B5CF6` |
| Primary hover | `#6D28D9` | `#9D7CFA` |
| Primary dark | `#5B21B6` | `#7C3AED` |
| Accent | `#A78BFA` | `#B9A2FF` |
| Primary soft | `#F5F3FF` | violet at 12% opacity |
| On-brand foreground | `#FFFFFF` | `#FFFFFF` |
| On-brand muted | `#DDD6FE` | `#DDD6FE` |

Violet is reserved for KAORI identity, active navigation, selected state, focus, primary actions, contextual metadata, and restrained analytical emphasis. It must not replace operational semantic colors.

## Functional tokens

Use functional token names rather than literal color names.

### Surfaces

- `surface-page`
- `surface-sunken`
- `surface-shell`
- `surface-sidebar`
- `surface-card`
- `surface-muted`
- `surface-elevated`
- `surface-hover`
- `surface-selected`
- `surface-overlay`

### Content

- `content-primary`
- `content-secondary`
- `content-muted`
- `content-disabled`
- `content-inverse`

### Outlines

- `outline-subtle`
- `outline-default`
- `outline-strong`
- `outline-focus`

## Dark mode

KAORI dark mode follows **neutral-first surfaces with controlled Violet**. The surface order is `page → shell → card → elevated`; Bright Violet is reserved for focus, primary interaction, selected state, and small identity accents. Large repeated surfaces remain neutral. A sparse explicit workspace/domain handoff may use the shared deep-Violet `.kaori-brand-domain-panel` (for example `Related Page Card`). The Welcome capability anchor is the one product-landing exception that reuses the exact `.kaori-hero-shell` surface, including dark mode, to keep the catalog visually tied to the Hero. Page-local Violet surfaces are not allowed.

The exact palette, Hero exception, sidebar treatment, prohibited patterns, and enforcement procedure are owned by `docs/design/components/DARK_MODE.md`. Page and module documentation may not redefine dark tokens.

## Global semantic color contract

| Family | Strong / icon | Text | Soft background | Border reference |
|---|---|---|---|---|
| Primary Violet | `#7C3AED` | `#6D28D9` | `#F5F3FF` | `#C4B5FD` |
| Info | `#2563EB` | `#1D4ED8` | `#EFF6FF` | `#BFDBFE` |
| Normal | `#059669` | `#047857` | `#ECFDF5` | `#A7F3D0` |
| Warning | `#D97706` | `#B45309` | `#FFFBEB` | `#FDE68A` |
| Critical | `#DC2626` | `#B91C1C` | `#FEF2F2` | `#FECACA` |
| Neutral | `#64748B` | `#475569` | `#F8FAFC` | `#CBD5E1` |

Canonical state mapping:

| State | Family |
|---|---|
| Healthy, Ready, Connected, Active | Normal |
| Informational, Advisory, Pending, Syncing, Processing | Info |
| Warning, Degraded, Partial, At Risk, Maintenance, Paused, Silenced | Warning |
| Critical, Failed, Down, Blocked, Destructive | Critical |
| Unknown, Not Collected, Not Evaluated, Disabled, Inactive, Not Configured | Neutral |

Aggregated precedence:

`Critical > Warning > Info/Pending > Neutral/Unknown > Normal`

Missing data must never render as healthy. Decorative icons, provider names, environment names, and neutral counts do not use operational semantic colors.

## Typography

Use Inter through the global `font-sans` token.

| Role | Standard |
|---|---|
| Page title outside hero | 24–28 px, 700 |
| Section title | 18 px, 700 |
| Card title | 15–16 px, 600–700 |
| Body | 14 px, 400 |
| Supporting text | 12–13 px, 400 |
| Table content | 13–14 px, 400–600 |
| Compact label | 10–11 px, 600–700 |

Endpoints, resource identifiers, IP addresses, namespaces, and hashes use the application sans-serif family in ordinary UI. Monospace is reserved for code blocks, query editors, payload editors, and evidence where character alignment is part of the task.

Hero typography is defined exclusively in `docs/design/components/HERO.md`.

## Spacing and density

Use the Tailwind spacing scale with the primary rhythm:

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 px`

KAORI uses comfortable-compact density suitable for operational work at 100% browser zoom. Avoid both marketing-style whitespace and cramped control groups.

## Shape and elevation

- Page-level form controls, action buttons, navigation rows, and ordinary icon surfaces: 8 px (`rounded-lg`).
- Compact table filters, table actions, pagination controls, and status/metadata labels: 6 px (`rounded-md`).
- Standard cards, dropdown/menu surfaces, and expandable supporting content: 12 px (`rounded-xl`).
- Sidebar frame, main application frame, hero, primary Info Flow, Related Page Card, and large grouped surfaces: 16 px (`rounded-2xl`).
- Status and metadata labels are borderless and never pill-shaped.
- A compact icon + border label is a documented special-label exception and must use the shared special-label component; it is not the default status treatment.
- Full radius is reserved for avatars, status dots, toggles, and progress tracks where the shape has semantic purpose.
- Avoid `rounded-3xl` and arbitrary authenticated-shell radii above 16 px.

Elevation:

1. Flat — internal sections and tables.
2. Card — standard content surfaces.
3. Elevated — menus, dialogs, drawers, and floating panels.

Dark mode relies primarily on surface and outline separation, not heavy shadows.

## Interaction states

Every interactive component defines:

- default
- hover
- focus-visible
- active
- selected
- disabled
- loading
- error or success where applicable

Use a visible violet focus ring with a surface-colored offset. Functional transitions normally use 150–220 ms.

## Application shell

- Use `surface-page` with a compact outer gutter.
- The desktop sidebar is 250 px when open and may be fully hidden; do not introduce an icon-only rail unless separately approved.
- The sidebar uses `surface-sidebar`; violet is reserved for active state, focus, brand icon, and restrained highlights.
- Sidebar and main application frame use a 16 px outer radius.
- Active navigation uses solid Violet in light mode and a translucent Violet surface with a left accent in dark mode; both retain readable white/inverse identity.
- Nested navigation uses compact rows, a low-contrast guide, and violet selected state.
- The main frame and navbar use `surface-shell`; cards use `surface-card`; menus, dialogs, and drawers use `surface-elevated`.

## Global component contracts

Detailed component rules are maintained separately:

- Dark mode: `docs/design/components/DARK_MODE.md`
- Hero: `docs/design/components/HERO.md`
- Tables and compact labels: `docs/design/components/TABLE_AND_LABEL.md`
- Related page relationships: `docs/design/components/RELATED_PAGE_CARD.md`
- Right contextual rail: `docs/design/components/RIGHT_CONTEXT_RAIL.md`
- Form + right context: `docs/design/components/FORM_WITH_CONTEXT_RAIL.md`
- View More Content: `docs/design/components/VIEW_MORE_CONTENT.md`
- Form submission actions: `docs/design/components/FORM_ACTION_BAR.md`
- Operational action feedback: `docs/design/components/OPERATIONAL_ACTION_FEEDBACK.md`
- Reusable page composition: `docs/design/patterns/`

A page must consume shared components rather than recreate their utility strings.

## Responsive behavior

- Preserve information hierarchy across breakpoints.
- Reflow columns vertically without changing semantic order.
- Primary page identity remains before metadata and actions.
- Controls may wrap but must keep stable height and alignment within their component contract.
- Avoid breakpoint-specific page-local geometry when a shared pattern already exists.

## Accessibility

- Each page has one authoritative `h1`.
- Text and controls meet WCAG AA contrast.
- Keyboard focus is visible.
- Icon-only actions have accessible names.
- Status and metadata never rely on color alone.
- Disabled controls remain legible and distinguishable from unavailable data.
- Motion is restrained and does not obscure state changes.

## Loading, empty, error, and permission states

- Loading indicators appear in the affected content region, not by replacing stable page identity.
- Empty states explain what is absent and identify the next valid action when one exists.
- Errors use concise user-facing language; detailed technical evidence belongs in Activity Audit Log or a detail view.
- Unknown, unavailable, permission denied, and not configured are separate conditions.
- Permission-restricted actions are hidden or disabled according to the authorization contract; visual treatment must not imply that authorization is merely a temporary loading state.

## Global naming convention

- User-facing environment names use canonical full names, never abbreviations.
- Examples: `Development`, `Staging`, `Production`, `Quality Assurance`, and `User Acceptance Testing`.
- Legacy aliases may be accepted as input but are normalized before display.
- Templates use the shared environment formatter rather than local title-casing or `if` mappings.
- Provider, capability, lifecycle, and status terminology must use canonical vocabulary defined by the owning domain.

## Tailwind workflow

```bash
npm ci
npm run build-css
npm run watch-css
```

`frontend/styles.css` is the supported Tailwind entrypoint. Keep `package-lock.json` committed so `npm ci` remains deterministic.

## Global review checklist

Validate each redesign in:

- light mode
- dark mode
- 1366×768
- 1440×900
- 1920×1080
- 100% browser zoom
- loading, empty, error, disabled, unknown, and permission states
- keyboard navigation and focus rings
- open and closed navigation shell
- shared component compliance
- absence of raw template hex colors and page-local component geometry

## Documentation boundary

The following do **not** belong in this global document:

- page names used as mandatory templates
- domain-specific table columns
- provider-specific workflow instructions
- exact dashboard metrics
- module-specific buttons or route names
- Kubernetes object-specific detail-card layout
- authentication-provider availability
- module-specific empty-state copy

Place those rules in `docs/modules/` or the owning module README. Reusable structures that apply across multiple domains belong in `docs/design/patterns/`.


## Hero context-panel baseline

The Node Inventory right-side hero panel is the baseline for compact operational posture panels. Alertmanager Integrations and other applicable pages must use the shared `page_hero` context-panel macros. Human-readable hero metadata uses Title Case while technical identifiers preserve canonical casing. See `components/HERO.md`.


## Form + Right Context

Use the shared Form + Right Context pattern for focused create, edit, register, and configuration tasks where one primary form remains dominant and concise workflow/safety/reference guidance belongs beside it. The canonical desktop geometry is the proven Integration registration `8/12 + 4/12` split. New reviewed consumers must use `components/form_with_context_rail.html`; do not copy the grid classes into page templates. Existing Kubernetes, Metrics Source, and Alertmanager registration pages remain visual references and should migrate to the shared geometry during their Integration final recheck without changing appearance. See `components/FORM_WITH_CONTEXT_RAIL.md`.

## Info Flow

Use the shared Info Flow component for short ordered governance or operational sequences. The standard structure is an expandable header, a three-to-five-step vertical timeline, and one optional flow-wide boundary note. Role Assignment Flow, Alertmanager Registration Flow, and Metrics Source Configuration Flow are reference implementations. See `components/INFO_FLOW.md`.



## Context Guidance Card

Use the shared Context Guidance Card for compact secondary **ordered** guidance in the right-side contextual column of create, edit, detail, configuration, and validation workspaces. The After Registration card on Register Alertmanager Instance is the reference implementation. The component uses native expandable behavior, two to five concise steps, generated two-digit markers, and no embedded actions. It is normally closed; use the default-open state only when the guidance is essential and no separate primary Info Flow exists. See `components/CONTEXT_GUIDANCE_CARD.md`.

## Information Guide Card

Use the shared Information Guide Card for non-sequential option, concept, ownership-model, or contract references in contextual sidebars. Every peer item uses a related icon, Title Case label, and concise sentence-case explanation. Do not use numbering, arrows, or timeline connectors because the items may be read in any order. Connection Type Guide on Register Alertmanager Instance is the reference implementation. See `components/INFORMATION_GUIDE_CARD.md`.

## Workspace Summary Card

Use the shared Workspace Summary Card for two to four peer summaries immediately below a tab bar or workspace header. Every card in the same row uses the same Violet Soft surface and Violet outline; do not emphasize only one equal summary through a local color variation. Configuration, Validation, Runtime, and Scope workspaces must reuse the same component when their summaries are peer-level. Alertmanager and Metrics Source Manage are reference implementations. A true warning or live state must use a semantic status component instead. See `components/WORKSPACE_SUMMARY_CARD.md`.

## Health Interpretation

Use the shared Health Interpretation component to translate a provider runtime score into current posture, fixed score ranges, readiness boundary, and contributing evidence. Keep runtime health separate from validation readiness, use semantic colors only for actual health meaning, and do not use oversized radial charts. Alertmanager and Metrics Source Runtime & History are reference implementations. See `components/HEALTH_INTERPRETATION.md`.

## Related Workspace Contract

When two KAORI pages form one operational or governance workflow, expose the relationship through the shared Related Page Card rather than an undocumented page-local shortcut. Place the card on contextual create, edit, detail, configuration, validation, or workflow subpages in the right-side column. Do not place it on overview, landing, list, or registry pages. A single-page module such as Roles & Access is the documented exception. The card provides exactly one destination action and preserves at least 24 px between the content and action. It uses intrinsic content height and must not stretch to match an unrelated neighboring form. See `components/RELATED_PAGE_CARD.md`.

## Connection Validation Header

Use the shared Connection Validation Header when a connection block exposes a reachability test, full validation, runtime refresh, or evidence-rebuild action. The helper is one short sentence, approximately 80 characters or fewer, and explains only the immediate operation. Detailed workflow or remediation information belongs outside the header. See `components/CONNECTION_VALIDATION_HEADER.md`.

## Operational Toggle

Use the shared Operational Toggle for connection boolean controls. Equivalent operational and security controls use the neutral baseline and identical geometry. Apply warning or critical colors only when enabling the option creates a documented exception or risk, such as allowing a legacy TLS certificate. See `components/OPERATIONAL_TOGGLE.md`.

## Destructive Confirmation

Use a KAORI critical modal for persisted-object deletion or detachment. Browser-native `confirm()` prompts are prohibited. The modal provides object identity, consequence copy, Cancel, one destructive action, Escape/backdrop handling, and focus return. Server-side lifecycle checks remain authoritative. See `components/MODAL_DRAWER.md`.

## Integration Manage Workspace

Use the shared Integration Manage Workspace for provider instance detail pages. Alertmanager is the reference implementation; Metrics Source follows the same four-tab architecture, inline Configuration flow, technical Validation & Capabilities matrix, Runtime & History presentation, and governed Scope & Resolution workspace. Provider-specific terminology and evidence remain explicit. See `components/INTEGRATION_MANAGE_WORKSPACE.md`.

## Operational mutation contract

Normal provider actions must persist Activity Audit evidence and return matching toast feedback. Same-page actions use HTMX and replace only the affected workspace partial. Successful actions that change resource location use `HX-Redirect`. Normal templates must not route users through legacy provider compatibility pages. See `docs/design/components/OPERATIONAL_ACTION_FEEDBACK.md`.
