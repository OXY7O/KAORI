# KAORI Design System v1

This document is the authoritative visual reference for KAORI interface work. New pages and redesigns must use the Tailwind design tokens defined in `frontend/styles.css`; page-specific color CSS is not allowed.

## Design direction

The visual concept is **KAORI Violet Infrastructure**: a modern enterprise interface with a violet brand identity, neutral operational surfaces, restrained elevation, and conventional infrastructure status semantics.

The interface must remain information-first. Violet establishes product identity and hierarchy, while health, readiness, risk, and process states retain their own semantic colors.

## Implementation contract

- Tailwind CSS v4 is the styling system.
- Design tokens are defined once in `frontend/styles.css`.
- Templates use semantic utilities such as `bg-surface-card`, `text-content-primary`, and `border-outline-default`.
- Do not introduce page-specific stylesheets for ordinary layout, spacing, typography, color, radius, shadow, or interaction states.
- Do not use raw hex colors in Jinja templates.
- Rebuild `app/static/css/output.css` after changing templates or design tokens.
- Light and dark mode must be validated together for every component.
- Status must never rely on color alone; pair it with a text label and, where useful, an icon.
- Authenticated application surfaces must not use linear, radial, or conic gradients. Use solid semantic tokens, borders, opacity layers, and restrained shadows to establish hierarchy.
- `bg-gradient-*`, `from-*`, `via-*`, `to-*`, and arbitrary gradient backgrounds are not allowed in new or redesigned authenticated pages.

## Brand palette

| Role | Light mode | Dark mode |
|---|---|---|
| Primary | `#7C3AED` | `#8B5CF6` |
| Primary hover | `#6D28D9` | `#9F7AEA` |
| Primary dark | `#5B21B6` | `#7C3AED` |
| Accent | `#A78BFA` | `#B9A2FF` |
| Primary soft | `#EDE9FE` | violet at 14% opacity |
| On-brand foreground | `#FFFFFF` | `#FFFFFF` |
| On-brand muted | `#DDD6FE` | `#DDD6FE` |

Authenticated KAORI interfaces use solid brand surfaces. The default hero surface is Primary `#7C3AED` in light mode and the corresponding `kaori-primary` token in dark mode. Gradients are not part of the approved application design language.

In dark mode, violet is an accent rather than the default surface color. Dark surfaces use charcoal-plum neutrals so controls, status, and data visualizations remain distinguishable.

## Surface and content tokens

Use functional token names instead of literal color names.

### Surfaces

- `surface-page`
- `surface-sidebar`
- `surface-card`
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

## Infrastructure status semantics

| State | Meaning | Visual family |
|---|---|---|
| Normal / Healthy / Ready / Connected | Function is operating as expected | Green |
| Informational / Advisory | Useful context without direct risk | Blue |
| Warning / Degraded / At Risk / Partial | Reduced function or meaningful risk requires attention | Amber |
| Critical / Failed / Down / Blocked | Unavailable, failed, blocked, or high impact | Red |
| Unknown / Not Collected / Not Evaluated | KAORI cannot determine current condition | Slate |
| Disabled / Inactive / Not Configured | Intentionally inactive or not configured | Muted slate |
| Maintenance / Paused / Silenced | Controlled operational state | Violet |
| Pending / Syncing / Processing | Work is still in progress | Cyan |

Aggregated status precedence:

`Critical > Warning/Degraded > Pending > Unknown > Normal`

Do not treat missing data as healthy. Disabled, unknown, pending, and degraded are distinct states and must remain distinct in both copy and presentation.

## Typography

Use Inter through the global `font-sans` token.

- Page title: 24–28 px
- Hero metric: 26–32 px
- Section title: 18 px
- Card title: 15–16 px
- Body: 14 px
- Supporting text: 12–13 px
- Table content: 13–14 px
- Badge: 11–12 px

Hero hierarchy:

- Eyebrow/label: 10 px, uppercase, `tracking-[0.14em]`, 32 px minimum height, 12 px horizontal padding, 6 px vertical padding, and 8 px radius (`rounded-lg`).
- Every authenticated hero eyebrow must use the shared `components/page_hero.html` macro. Do not recreate the label classes per page.
- Hero leading icon: 48 px on compact viewports and 56 px from `sm` upward, with a 16 px horizontal gap to the content column.
- Hero title: 32–48 px depending on viewport and content length.
- Hero secondary identity or role: 20–24 px.
- Hero description: minimum 15 px with 24 px line height.
- Eyebrow, title, secondary identity, description, supporting notice, and capability badges must start on one authoritative text-column edge. Use the shared two-column hero intro grid; do not align elements using manual `ml-*`, `pl-*`, arbitrary pixel offsets, or duplicated margin calculations.

Use the application sans-serif family for endpoints, resource identifiers, IP addresses, namespaces, and hashes when they appear in forms, tables, cards, or operational summaries. Monospace is reserved for dedicated code blocks, query editors, payload editors, and copyable technical evidence where character alignment is part of the task.

## Spacing and density

Use the Tailwind spacing scale. Prefer the following rhythm:

`4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 px`

KAORI uses a comfortable-compact density suitable for operational work at 100% browser zoom. Avoid marketing-style whitespace and avoid compressing labels, values, and actions into visually ambiguous groups.

## Shape and elevation

KAORI uses a restrained three-level radius scale for authenticated operational interfaces:

- Compact controls, navigation rows, and icon surfaces: 8 px (`rounded-lg`)
- Standard cards, topbar controls, brand cards, and dropdowns: 12 px (`rounded-xl`)
- Sidebar frame, main application frame, hero, and large grouped surfaces: 16 px (`rounded-2xl`)
- Avatars, status dots, toggles, and progress tracks: full radius only where the shape has semantic purpose
- Status and metadata labels: compact 6 px rectangular radius (`rounded-md`), never pill-shaped

Avoid `rounded-3xl` and arbitrary radii above 16 px in the authenticated application shell. Larger promotional radii may be used only on isolated marketing or authentication compositions when explicitly approved. Do not nest multiple large rounded wrappers around the same content hierarchy.

Elevation levels:

1. Flat: internal sections and tables
2. Card: standard content surfaces
3. Elevated: menus, dialogs, and floating panels

Dark mode relies primarily on surface and outline separation, not heavy shadows.

## Interaction states

Every interactive component must define:

- default
- hover
- focus-visible
- active
- selected
- disabled
- loading
- error or success where applicable

Use a violet focus ring with a surface-colored offset. Keep transitions functional and short, normally 150–220 ms.

## Login page reference

The login page is the first implemented reference for the design system.

- Split layout on desktop; form-first layout on smaller screens.
- Violet brand panel with infrastructure-oriented visual context.
- White or neutral form surface using semantic surface tokens.
- Use comfortable-compact density and keep the complete desktop card usable at 100% browser zoom on a 1366×768 laptop viewport.
- Prefer `max-w-5xl`, compact vertical padding, 44 px controls, and restrained illustration height for authentication layouts.
- The login brand panel uses a CSS-only infrastructure composition built from Tailwind utilities and Lucide icons. Do not depend on raster artwork for the core login layout.
- Keep brand-panel copy minimal: one eyebrow, one short headline, and at most one supporting line. Avoid embedded dashboard labels, marketing feature cards, and repeated copy.
- Use the `brand-foreground`, `brand-foreground-muted`, `brand-surface`, `brand-surface-strong`, and `brand-outline` tokens for content rendered on violet or dark brand surfaces.
- Decorative infrastructure visuals must use brand colors. Semantic status colors are reserved for real health, risk, connectivity, or process values.
- Local database authentication remains the only actionable provider until additional providers are implemented. Do not expose an SSO action before its authentication flow is available.
- Theme switching must work before authentication.
- Authentication errors use the critical semantic family; successful notices use the normal family.
- Security copy may describe RBAC and audit controls but must not imply unavailable authentication capabilities.

## Tailwind workflow

Install frontend dependencies once:

```bash
npm ci
```

Build CSS:

```bash
npm run build-css
```

Watch during development:

```bash
npm run watch-css
```

The production Docker build executes the same `build-css` script and copies the generated stylesheet into the runtime image.

`frontend/styles.css` is the only supported Tailwind entrypoint. Dev Container creation and startup rebuild the stylesheet automatically. The build then runs `scripts/verify_css_build.mjs`; it fails when required KAORI Violet Infrastructure tokens or generated utilities are missing. Keep `package-lock.json` committed so `npm ci` is deterministic in both the Dev Container and production image.

## Review checklist

Validate each redesign in:

- light mode
- dark mode
- 1366×768
- 1440×900
- 1920×1080
- 100% browser zoom
- loading, empty, error, disabled, and permission states where applicable
- keyboard focus and visible focus rings
- the open and closed navigation states used by the application shell

## Application shell reference

The authenticated application shell uses a floating, rounded navigation model rather than a full-bleed rectangular sidebar.

- Place the application shell on `surface-page` with a compact outer gutter.
- Use a 250 px sidebar at the standard desktop density when navigation is open. The navbar control may fully hide or restore the sidebar; do not introduce a narrow icon-only rail.
- The sidebar uses `surface-sidebar` as its foundation. Violet is reserved for the active item, focus state, brand icon, and restrained ambient highlights.
- Use a 16 px (`rounded-2xl`) outer radius for both the sidebar and main application frame.
- Keep navigation groups visually separated by compact uppercase labels; do not add decorative dividers between every item.
- Active navigation uses a filled violet state with white label and icon. Inactive items use muted on-brand content with a subtle translucent hover surface.
- Nested navigation remains inside the sidebar and uses a low-contrast vertical guide, compact rows, and a violet accent for the selected child.
- The navbar open/close control persists `kaori.sidebarOpen` locally and toggles the entire 250 px sidebar. The content frame expands into the released space when navigation is closed.
- The main application frame uses semantic surface and outline tokens in both light and dark mode. Avoid raw white, slate, blue, or violet utilities when a KAORI token exists.


## Table alignment

- All table headers and body cells are left aligned by default.
- The final column is right aligned. When it contains actions, action controls must also be grouped and aligned to the right edge.
- Do not center ordinary operational values, labels, or status descriptions.
- A table may deviate only when a domain-specific visualization explicitly requires another alignment and that exception is documented.

## Shared hero component

`app/templates/components/page_hero.html` is the authoritative implementation for authenticated hero structure and introductions.

- Use `page_hero.shell_classes()` for the outer authenticated hero surface.
- Use `page_hero.layout_classes()` for the standard 8/4 desktop grid and shared height contract.
- Use `page_hero.content_classes()` and `page_hero.aside_classes()` for the primary and supporting columns.
- Use `page_hero.intro(eyebrow_icon, eyebrow_label, leading_icon)` whenever a hero has an eyebrow and a leading icon.
- The standard Settings and Access hero shell uses `min-h-[15.5rem]` on compact layouts and a shared `lg:min-h-[17.5rem]` desktop baseline. The internal grid uses `lg:min-h-[14.5rem]` with the same 8/4 split for top-level workspaces and create/edit/detail workflows. User Management, Roles & Access, and Activity Audit Log are the primary height references. The hero uses minimum height rather than a fixed desktop height so wrapped metadata or longer context never gets clipped.
- The component owns the outer radius, border, solid brand surface, responsive padding, eyebrow geometry, icon sizing, column width, and horizontal gap.
- Page templates own only the title, optional role/subtitle, description, notice, badges, and context-panel content.
- Do not apply manual left margin or padding to compensate for the leading icon.
- Do not use `rounded-full` for hero eyebrows. Pills remain reserved for compact statuses, badges, filters, and metadata chips.
- Changes to hero geometry or alignment must be made in the shared component first, then validated across Settings, Access, Welcome, and Kubernetes Operations Dashboard reference pages.

- Settings and Access two-column forms must use `items-start` and self-sized cards. A primary configuration card must never stretch merely because the contextual rail contains longer guidance.
- Primary form actions and permission disclosures align to the same content-column width as the configuration card.

## Welcome workspace reference

The Welcome page is the reference implementation for the authenticated landing experience.

- Use a solid `kaori-primary` hero surface. Do not use a gradient or decorative color transition.
- The hero contains one primary welcome message and one role-aware access card. Do not add redundant status cards around it.
- Hero eyebrow, title, role, description, and capability badges use the shared `page_hero.intro()` grid and align to one authoritative text column. The eyebrow uses the standard 8 px rounded rectangle, not a pill.
- Hero description uses at least 15 px text with a 24 px line height so operational purpose remains readable on laptop displays.
- Use translucent on-brand surfaces for hero badges and access statistics.
- Keep the access card darker than the main hero so it reads as a secondary operational summary.
- Workspace groups use a two-part desktop composition: a violet group overview card and a neutral grid of actionable workspace cards. The outer group uses 16 px radius and internal cards use 12 px radius.
- Workspace cards remain neutral by default; violet appears on the icon, eyebrow, focus state, and hover action.
- Search, result count, permission filtering, and empty-state behavior must remain functional after visual changes.
- The Welcome page must use Tailwind utilities and shared tokens only. A page-specific `welcome.css` stylesheet is not part of the design contract.

## Kubernetes operations dashboard reference

The Kubernetes Operations Dashboard is the reference implementation for authenticated operational overview pages.

- Use a solid `kaori-primary` hero surface with a 16 px outer radius. Do not use a gradient. Keep the hero compact enough for a 1366×768 laptop viewport.
- The hero separates the page purpose from the operational context panel. The context panel contains cluster scope, source mode, and freshness time without introducing additional decorative status cards.
- The hero eyebrow, title, description, and scope notice use the shared `page_hero.intro()` grid and one authoritative text-column edge. The eyebrow uses the same 8 px rounded rectangle as Welcome.
- Dashboard hero descriptions use at least 15 px text with a 24 px line height.
- `All Clusters` represents inventory/database snapshot aggregation. Live Prometheus and AlertManager signals require a selected cluster and must be explained explicitly.
- KPI cards use neutral surfaces and semantic or brand icon treatments. Do not color an entire KPI card unless the whole card represents a real semantic status.
- Standard dashboard sections use 12 px outer radius, 8 px internal radius, semantic surfaces, and compact 20 px content padding.
- Dashboard sections remain expandable and default closed where detailed content is not required for the initial overview.
- Use violet for brand hierarchy and primary analytics emphasis. Use blue for secondary analytics series. CPU uses violet and memory uses blue consistently on dashboard consumer and capacity visuals.
- Infrastructure health, alert severity, source readiness, forecast risk, and report processing state use semantic status tokens rather than raw color utilities.
- Aggregated visual status follows `Critical > Warning/Degraded > Pending > Unknown > Normal`.
- Unknown, unavailable, not configured, and all-cluster limitations must remain distinct states. Missing data must never render as healthy.
- Cluster health is the primary non-collapsed operational table. It must display status reason, resource values, active alerts, source availability, and freshness context without excessive row height.
- Loading, empty, and cluster-required states use shared semantic tokens. Do not add page-level `<style>` blocks or page-specific stylesheets.
- Dynamic progress values may use a data-driven inline width because the value is computed at runtime; all visual color, shape, spacing, and typography remain controlled by Tailwind utilities and design tokens.

## Kubernetes Dashboard

- Non-dynamic dashboard iconography and decorative labels should default to KAORI violet rather than mixed semantic colors.
- Empty, unavailable, or cluster-required placeholder states on dashboard cards should use KAORI violet styling unless the content communicates a true operational status.

## Hero Standard

The KAORI authenticated hero is a frozen design-system component. Every page that requires a hero must use `app/templates/components/page_hero.html`; page-local hero geometry, typography, action styling, and alignment are prohibited.

### Final geometry and visual baseline

The active shared implementation is the authoritative baseline and supersedes the earlier experimental 164–188 px proposal.

- Compact viewport outer minimum height: **248 px** (`min-h-[15.5rem]`).
- Desktop outer target/minimum height from `lg`: **280 px** (`lg:min-h-[17.5rem]`).
- Internal compact grid minimum height: **208 px** (`min-h-[13rem]`).
- Internal desktop grid minimum height: **232 px** (`lg:min-h-[14.5rem]`).
- Outer padding: **20 px compact**, **24 px desktop**.
- Desktop grid: **7/5 columns**, representing approximately **58/42** rather than an arbitrary page-specific split.
- Column gap: **20 px**.
- Outer radius: **16 px**.

The shared minimum height preserves one visual horizon while allowing responsive wrapping. A normal desktop hero must visually remain at the 280 px baseline. Content that forces recurring growth beyond the baseline must be shortened or moved below the hero. A page may not introduce a smaller or taller local baseline.

### Authoritative typography

KAORI uses the global **Inter / `font-sans`** family for all hero content.

| Element | Compact/Desktop size | Weight | Line height | Additional rule |
|---|---:|---:|---:|---|
| Eyebrow | 10 px | 700 | 16 px | Uppercase, tracking `0.14em`, one line |
| Title | 30/32 px | 700 | 36/40 px | Tracking `-0.02em`, one line preferred, two maximum |
| Supporting description | 15 px | 400 | 24 px | One line minimum, two lines maximum |
| Metadata label | 11 px | 700 | Natural within 32 px min-height | Two minimum, three maximum |
| Supporting-strip label | 10 px | 700 | 16 px | Uppercase, tracking `0.12em` |
| Supporting-strip text | 12 px | 400 | 20 px | Short operational context only |
| Hero action | 14 px | 600 | 20 px within 40 px height | Full text label; no unexplained abbreviation |
| Compact posture metric label | 11 px | 600 | 16 px | Maximum four metrics |
| Compact posture metric value | 20–24 px | 700 | 28–32 px | Semantic status where applicable |

Use the shared macros:

- `page_hero.title_classes()`
- `page_hero.description_classes()`
- `page_hero.metadata_row_classes()`
- `page_hero.action_group_classes()`
- `page_hero.primary_action_classes()`
- `page_hero.secondary_action_classes()`
- `page_hero.destructive_action_classes()`

Do not copy these utility strings into page templates.

### Supporting-description contract

The supporting description states the operational purpose of the page.

- Minimum: one meaningful line, normally **60 characters or more**.
- Maximum: two rendered lines, normally **120 characters or fewer**.
- Recommended desktop content width: **620–704 px**; the shared class caps it at `44rem`.
- Use active, direct language such as `Register, validate, and manage...` or `Review and govern...`.
- Do not include implementation internals, full workflows, remediation steps, endpoint details, or multi-sentence guidance.
- When localization or a narrow viewport produces additional wrapping, the copy remains semantically concise; do not truncate essential meaning merely to satisfy a physical character count.

### Metadata-label contract

Every normal hero contains **two or three** contextual metadata labels.

Preferred order:

1. Environment or scope.
2. Provider, mode, object type, or page context.
3. Count, source role, compatibility profile, or other operational metadata.

Rules:

- Use `page_hero.meta_label()`.
- Use full environment names: `Development`, `Staging`, `Production`, and other canonical values.
- Metadata uses KAORI Violet because it communicates identity or context.
- Dynamic health, severity, readiness, failure, and process state use semantic status components instead.
- Empty collections use factual metadata such as `0 Connections`; do not use a misleading health label such as `Healthy`.
- Metadata labels are borderless, rectangular, and never pills.

### Hero action contract

The right-side primary hero action uses a white surface, natural hover treatment, and KAORI Violet text.

- Primary: white background, Violet text, subtle white/brand border, soft Violet hover, visible Violet/white focus ring.
- Secondary: translucent neutral surface on the Violet hero.
- Destructive: Critical semantic treatment; never Violet.
- Height: **40 px**.
- Horizontal padding: **16 px**.
- Ideal action count: one primary plus one secondary.
- Maximum visible actions: three. Additional actions move to a labelled overflow menu.
- Action order: primary operational action, secondary navigation/refresh action, destructive action last.
- Icon-only controls require an accessible name; normal hero actions should retain visible text.

### Official hero types

Only the following five types are permitted. These types share the same geometry, typography, semantic treatment, and component contract.

#### Standard Hero

Default for lists, settings, reports, governance, operations, and general module pages.

- Left: identity, purpose, two or three metadata labels.
- Right: actions or a compact contextual panel.
- No progress indicator, chart, or workflow detail.

#### Dashboard Hero

For operational overview and analytics overview pages.

- May include one compact posture panel containing no more than four metrics.
- Metrics summarize the current scope; they do not reproduce dashboard sections.
- Expensive live analytics and detailed trends remain below the hero.

#### Workspace Hero

For ongoing operational workspaces such as integration management, report generation, and protected workflows.

- May show current object identity, lifecycle context, and a compact posture summary.
- Workflow instructions, diagnostics, remediation, and historical evidence remain below the hero.

#### Wizard Hero

For create, register, import, and guided setup workflows.

- May show current step and short phase context.
- Progress is textual or compact; the full wizard and validation detail remain in the page body.
- The hero remains the same height when moving between steps.

#### Detail Hero

For a single managed object such as a cluster, user, integration instance, node, or namespace.

- Prioritizes object identity, environment/scope, provider/type, and lifecycle context.
- Provides only the most important object actions.
- Detailed properties and operational evidence remain below the hero.

Do not create a sixth type. A specialized workflow must select the closest official type and use content slots below the hero for domain-specific detail.

### Empty Hero

The hero does not become an empty-state component and must never disappear because no records exist.

- Keep eyebrow, title, purpose description, metadata, and the relevant creation/registration action.
- Use factual metadata such as `0 Connections`, `0 Reports`, or `No Active Binding` where context requires it.
- Render the explanatory empty state in the content region below the hero.
- Do not replace the hero with a large empty illustration or duplicate the same no-data message in both areas.

### Busy Hero

The hero remains static during HTMX requests, filtering, polling, pagination, runtime refresh, validation, synchronization, and background processing.

- Loading indicators belong to the affected content card or operation control.
- Do not replace, hide, collapse, dim, skeletonize, or reload the entire hero.
- Disable only the action that cannot safely be repeated, while retaining its dimensions and label context.
- A busy process may update a compact textual state after completion, but it must not change hero geometry.

### Hero stability

Hero stability is a functional requirement, not merely a visual preference.

The following must remain stable during dynamic operations:

- Outer height and padding.
- Leading-icon position.
- Eyebrow, title, description, and metadata alignment.
- Action-group position and button dimensions.
- Right-panel dimensions.

Dynamic values must reserve sufficient width or use stable wrapping. Filters, polling, runtime updates, and pagination must not cause the title, metadata, action group, or context panel to jump between rows. Long values should be shortened through canonical display names or moved into detailed content, not compensated with local geometry changes.

### Hero content rule

Every hero answers exactly five questions:

1. **Where am I?** — eyebrow.
2. **What page or object is this?** — title.
3. **What is its purpose?** — supporting description.
4. **What is the current context?** — two or three metadata labels and, when justified, one compact posture panel.
5. **What is the primary action?** — right-side action group.

Content that does not answer one of these questions belongs below the hero. In particular, do not place full technical diagnostics, remediation guidance, audit history, filter forms, long operational workflows, capability matrices, or explanatory documentation inside the hero.

Information hierarchy is fixed:

`Identity → Purpose → Context → Action`

### Information density and right-side panel

A standard hero may contain:

- One eyebrow.
- One title.
- One supporting description.
- Two or three metadata labels.
- Up to two normal actions, with three as the absolute visible maximum.
- Optionally, one compact right-side panel with up to four metrics.

The panel must not become a mini-dashboard. Long descriptions, tables, charts, progress bars, and diagnostic lists are prohibited in the hero panel.

### Responsive behavior

- Desktop: left content and right context/action region use the shared 7/5 grid.
- Tablet and mobile: right content stacks after identity, purpose, and metadata.
- Reading order remains eyebrow → title → description → metadata → supporting context/action.
- Actions never move above the title.
- Buttons retain a 40 px minimum height and remain keyboard accessible.
- Responsive wrapping may increase natural document height, but no page may introduce custom breakpoint geometry.

### Accessibility and performance

- The page title is the single authoritative `h1`.
- Text and controls meet WCAG AA contrast.
- Focus indicators remain visible against the Violet hero surface.
- Icons are supplemental; labels and status wording communicate meaning independently of color.
- Hero content uses lightweight page context already required for navigation. Heavy runtime queries, charts, history, and large aggregates are loaded in the content area.
- HTMX targets should exclude the hero unless navigation changes the page or managed object.

### Compliance checklist

A hero is compliant only when all applicable statements are true:

- Uses the shared `page_hero.html` component and macros.
- Uses one of the five official hero types.
- Uses the 248 px compact and 280 px desktop baseline.
- Uses Inter and the authoritative typography sizes.
- Has one `h1`, no more than two title lines, and no more than two description lines.
- Has two or three metadata labels in the prescribed order.
- Uses full environment names.
- Uses the white/Violet primary hero action treatment.
- Uses semantic colors for operational state and Critical for destructive actions.
- Contains no heavy query, chart, table, diagnostic list, or long workflow.
- Remains stable during HTMX, polling, filtering, pagination, and runtime updates.
- Preserves responsive reading order and visible keyboard focus.
- Contains no page-local hero geometry or duplicated typography classes.

Any exception requires a documented design-system decision before implementation.

## Semantic color and label contract

The final KAORI semantic palette applies globally to every workspace. Alertmanager, Prometheus, and Kubernetes remain reference implementations, but no page may define an alternative operational status palette.

| Family | Strong / icon | Text | Soft background | Border reference |
| --- | --- | --- | --- | --- |
| Primary Violet | `#7C3AED` | `#6D28D9` | `#F5F3FF` | `#C4B5FD` |
| Info | `#2563EB` | `#1D4ED8` | `#EFF6FF` | `#BFDBFE` |
| Normal | `#059669` | `#047857` | `#ECFDF5` | `#A7F3D0` |
| Warning | `#D97706` | `#B45309` | `#FFFBEB` | `#FDE68A` |
| Critical | `#DC2626` | `#B91C1C` | `#FEF2F2` | `#FECACA` |
| Neutral | `#64748B` | `#475569` | `#F8FAFC` | `#CBD5E1` |

Usage rules:

- Violet is reserved for active navigation, primary actions, focus state, selected state, and KAORI identity.
- Health, readiness, validation outcome, risk, connectivity, and destructive state use their semantic family; they must not be represented as violet merely to match the brand.
- Border-reference colors remain available for semantic panels, callouts, dialogs, destructive controls, and other containers that require separation.
- Compact status and metadata labels are borderless. Their soft background, semantic text, and optional semantic icon provide the state distinction.
- Do not apply status colors to decorative icons, ordinary metadata, environment names, provider names, or neutral counts.

## Table label sizing

`app/templates/components/table_label.html` is the authoritative implementation for compact labels inside operational tables.

- Status labels use `table_label.status_label()` or the shared integration `status_badge()` macro and use the semantic family matching the operational state.
- Metadata labels use `table_label.metadata_label()` and use Primary Violet because they describe identity or context rather than health.
- Status and metadata labels use a 6 px rectangular radius and no visible border in the Alertmanager and Prometheus rollout scope.
- Standard label geometry is 24 px minimum height, 8 px horizontal padding, 2 px vertical padding, 10 px semibold text, 16 px line height, 4 px internal gap, and a 12 px icon.
- Do not create page-specific badge sizes. Integration health, readiness, compatibility, runtime state, source role, and contextual metadata consume the shared compact size.
- Timestamp text is not a label; render the timestamp separately and place the compact state label beside or below it only when needed.

## Kubernetes topology reference

The Kubernetes Topology workspace follows the same Inventory hero and operational workspace rules while allowing distinct graph colors for data visualization.

- Use the shared `page_hero.intro()` structure with a solid `kaori-primary` hero, aligned eyebrow/title/description, and rectangular metadata labels for cluster, namespace, and resource counts.
- Topology summary metrics and last-collected context use translucent brand surfaces. They are inventory context, not health statuses.
- Workspace headers, toolbar icons, filter focus states, resource visibility icons, search results, empty states, and drawer navigation use KAORI violet.
- Relationship line colors and resource node colors may remain distinct only inside the graph or legend where color is necessary to differentiate data categories. Those colors must not leak into generic buttons, filters, labels, or navigation controls.
- Health and collection states use semantic status tokens. Loading uses Pending, graph truncation uses Warning, startup failure uses Critical, and unknown resource state uses Unknown.
- Topology filter labels use sentence case, `text-sm font-semibold`, 44 px controls, 8 px radius, and shared surface/outline tokens.
- The graph workspace uses 12 px outer radius and 8 px internal control radius. Detail cards use 12 px radius; icon surfaces and buttons use 8 px radius.
- Non-status resource and relationship labels in the detail drawer use rectangular metadata labels. Only dynamic health/status labels remain pill-shaped.
- Empty graph and unselected-detail states use violet surfaces. Do not render missing inventory as Healthy.
- The graph viewport height is controlled by Tailwind layout utilities rather than page-level inline CSS. JavaScript may update runtime dimensions only when required by the visualization library.

## Kubernetes node inventory reference

The Node Inventory page follows the authenticated Inventory standard and is the reference for resource inventory pages with expandable operational details.

- Use a solid `kaori-primary` hero with the shared `page_hero.intro()` alignment. Node count, CPU, and memory are rectangular hero metadata labels, not status pills.
- The hero posture panel presents Ready and Not Ready counts using the Inventory Overview metric geometry. The aggregated readiness result is shown as a semantic label in the panel header, while the panel footer uses the standard `Manage Clusters` action used across Inventory heroes.
- Capacity cards use neutral surfaces with violet labels and icons. A single solid violet highlight card may be used for the primary readiness ratio; gradients are prohibited.
- Node table filters use sentence case, 44 px controls, 8 px radius, and shared surface/outline tokens.
- Table columns are left aligned except the final Details column, which is right aligned. Cluster and Role are metadata labels; node readiness is a semantic status label.
- Expandable node details use 12 px cards, violet non-status icons, compact shared labels, and semantic colors only for readiness, pressure, scheduling, network availability, and other dynamic states. All key/value rows use the same sans-serif 12 px typography and 20 px line height; UUIDs, IP addresses, and runtime identifiers may use break-all wrapping but must not switch to a monospace font.
- Node labels are descriptive metadata and use violet rectangular labels. Taints remain visually prominent because they affect scheduling behavior.
- Node empty, unavailable, and uncollected states use the shared violet empty-state treatment. Missing data must not render as Healthy.

## Kubernetes namespace inventory reference

The Namespace Inventory page follows the same hero geometry, operational table density, and expandable-detail standard as Inventory Overview and Node Inventory.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Namespace count, contributing clusters, and active namespace count are hero metadata and use rectangular brand labels. The aggregate lifecycle posture is the only semantic label in the hero panel.
- Coverage cards use neutral surfaces with violet labels and icons. Active and non-active lifecycle counts may use semantic icon treatments because they communicate real status.
- The primary active-coverage card may use a solid dark-violet surface and a runtime progress width. Gradients are prohibited.
- Namespace table columns are left aligned except the final Details column, which is right aligned. Cluster identity and additional control counts are metadata labels; namespace lifecycle and collection/control availability use compact semantic labels.
- Filters use sentence case, 44 px controls, 8 px radius, shared surface tokens, and violet focus states. Loading bars use a solid violet fill.
- Expandable namespace details use 12 px cards, 8 px icon surfaces, consistent sans-serif 12 px key/value typography, and the shared compact label component. UID values may wrap with `break-all` but must not switch to monospace.
- ResourceQuota, LimitRange, Default ServiceAccount, and namespace lifecycle are dynamic states and use semantic labels. Workload composition, PSA policy values, object counts, labels, and annotations are metadata and use violet or neutral styling.
- Namespace labels are descriptive metadata and use rectangular violet labels. Empty labels, annotations, or quota collections use the shared violet empty-state treatment rather than warning colors.


### Nested detail empty states

- Empty nested sections inside inventory detail cards use a compact dashed information box, not an otherwise empty solid object card.
- Use the KAORI soft surface, violet icon/title, and one short explanatory sentence describing what was not collected or configured.
- Render the normal solid object card only when the nested section contains actual records or configuration values.

### Inventory detail card bottom stack

In expandable Inventory detail cards, secondary object summaries such as Workload Composition, ResourceQuota details, and Pod Security Admission must be anchored in the lower card region immediately above the informational tip. Primary key/value rows remain at the top. Use one `mt-auto` bottom stack containing the secondary object block followed by the tip so sibling cards keep a consistent visual rhythm.

## Kubernetes workload inventory reference

The Workload Inventory page follows the same resource-inventory baseline as Inventory Overview, Nodes, and Namespaces.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Workload count, Deployment count, and Running count are contextual hero metadata and use rectangular brand labels. The aggregate lifecycle result is the only semantic label in the hero panel.
- Coverage cards use neutral surfaces with violet labels and icons. The primary running-coverage card may use a solid dark-violet surface and runtime progress width; gradients are prohibited.
- Workload table columns are left aligned except the final Details column, which is right aligned. Cluster, namespace, workload type, and update strategy are metadata; lifecycle state is a compact semantic label.
- Filters use sentence case, 44 px controls, 8 px radius, shared surface tokens, and violet focus states. Loading bars use a solid violet fill.
- Expandable workload details use 12 px cards, 8 px violet icon surfaces, consistent sans-serif 12 px key/value typography, and compact shared labels. Kubernetes UID and long image or annotation values may wrap but must not switch to a different typography scale.
- Container kind, pull policy, workload labels, placement constraints, node selectors, and tolerations are descriptive metadata and use rectangular violet labels. Workload, Pod, and rollout state use semantic status labels.
- Empty nested sections use compact dashed information boxes. Informational boundaries use violet; missing required collection data may use Warning when operator action is required.

## Kubernetes Pod inventory reference

The Pod Inventory page follows the Inventory Overview hero geometry and the resource-inventory interaction standard used by Nodes, Namespaces, and Workloads.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Pod count, Running count, and unique image count are contextual hero metadata and use rectangular brand labels. The aggregate Pod posture is the only semantic label in the hero panel.
- Runtime summary cards use neutral surfaces with violet labels and icons. The primary Running coverage card may use a solid dark-violet surface with a runtime progress width; gradients are prohibited.
- Pod table columns are left aligned except the final Details column, which is right aligned. Cluster, namespace, and owner type are metadata labels. Phase and readiness are compact semantic status labels.
- Filters use sentence case, 44 px controls, 8 px radius, shared surface tokens, and violet focus states. Loading bars use a solid violet fill.
- Expandable Pod details use 12 px cards, 8 px violet icon surfaces, consistent sans-serif 12 px key/value typography, and compact shared labels. Kubernetes UID, Pod IP, Host IP, image references, volume sources, and annotation values may wrap but must not switch typography scale.
- The primary detail cards are Pod identity, Placement & network, Pod conditions, and Pod configuration. Their information tips use the same height and bottom alignment.
- Container kind, image pull policy, owner type, volume type, mount targets, Pod labels, node selectors, and tolerations are descriptive metadata and use rectangular violet labels. Pod phase, readiness, container state, and collection warnings use semantic status labels.
- Empty nested sections use compact dashed information boxes. Missing runtime detail that requires a worker restart or resync uses Warning; ordinary unconfigured or empty metadata uses the violet empty-state treatment.


## Pod condition subcards and tips

- Nested condition headings use 11 px semibold text; condition names use 10 px medium text with 16 px line-height.
- Compact table status labels remain 10 px and should not be enlarged inside nested detail cards.
- Equal-height primary tips use a compact minimum height and concise operational copy.


## Nested inventory object summaries

- Workload Composition is the visual reference for secondary object summaries inside expandable Inventory cards.
- Use the shared `components/detail_object.html` component: a violet soft surface, 8 px radius, 24 px icon surface, 12 px title and rows, and a compact rectangular metadata badge.
- Render only configured or meaningful rows in the object summary. Do not fill the block with zero-value or `Not configured` rows.
- When no records or constraints exist, replace the solid object summary with the shared centered dashed empty state containing a violet icon, a short title, and one concise sentence.
- Apply this pattern to Pod Placement constraints, Pod Reported conditions, Workload Delivery & placement constraints, and future equivalent nested summaries.
- Workload Runtime state should show a compact controller summary rather than every collector field. Keep the most operationally useful four state values plus Managed Pods; detailed historical behavior remains in Analytics.

## Kubernetes Service inventory reference

The Service Inventory page follows the same resource-inventory baseline as Inventory Overview, Nodes, Namespaces, Workloads, and Pods.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Service count, internal Service count, and external exposure count are contextual hero metadata and use rectangular brand labels. The aggregate exposure posture is the only semantic label in the hero panel.
- Networking summary cards use neutral surfaces with violet labels and icons. The primary internal-coverage card may use a solid dark-violet surface and runtime progress width; gradients are prohibited.
- Service table columns are left aligned except the final Details column, which is right aligned. Cluster, namespace, Service type, and port summary are metadata labels. Endpoint readiness is a compact semantic status label.
- Filters use sentence case, 44 px controls, 8 px radius, shared surface tokens, and violet focus states. Loading bars use a solid violet fill.
- Expandable Service details use 12 px cards, 8 px violet icon surfaces, consistent sans-serif 12 px key/value typography, compact shared labels, and the shared nested-object pattern for selectors and empty collections.
- Service type, protocol, application protocol, selectors, labels, and other descriptive values are metadata and use rectangular violet labels. Endpoint and selected-Pod runtime state use semantic status labels.
- Endpoint addresses, selected Pods, labels, annotations, and port mappings use neutral containers with violet non-status iconography. Empty or unconfigured nested sections use the shared dashed violet information state. Missing required collection metadata may use Warning.


## Inventory expandable-card tips

- Every populated card or section inside an Inventory View More panel must end with one concise informational tip. Existing tips remain unchanged; add the shared `components/inventory_detail_tip.html` treatment only where a card has no guidance.
- Place the tip at the bottom of the card after primary values and nested object summaries. Header, content, nested summary, then tip is the required visual order.
- Use the KAORI soft violet surface, 8 px radius, violet icon, 12 px body text, and one short operational sentence. Avoid repeating the section description or filling the card with explanatory prose.
- Nodes Inventory View More is the typography baseline: tip title and body both use 12 px text with 20 px line-height; titles may use semibold weight while body copy remains regular. Use a 24 px icon surface with a 14 px icon, 12 px horizontal padding, and 10 px vertical padding. Do not use 11 px body copy inside Inventory tips.
- All Inventory tip variants, including titled information boxes and warning guidance, must render through `components/inventory_detail_tip.html`. Page-local macros may only delegate to the shared component and must not redefine typography.
- A dashed empty-state box may replace the separate tip when the section has no records because it already explains the missing or unconfigured state. When records are present, the persistent bottom tip is required.
- Tips describe data meaning or snapshot boundaries. They must not introduce warning colors unless operator action is required.

### Inventory detail card density

- View More cards reserve explicit vertical space according to content density instead of forcing one universal height.
- Standard cards use approximately 20–24 rem; cards containing nested objects or condition lists use approximately 28–32 rem.
- Tips are pinned to the bottom with a dedicated 12 px separation and must never flex-shrink into the content above.
- Dense cards may grow beyond their minimum height when runtime data contains additional rows. Empty-state boxes replace redundant tips rather than stacking two explanatory boxes.

### Nested object and tip separation

- A nested object summary and its following information tip must never touch.
- Use the shared `detail_object.stack()` wrapper or an equivalent `space-y-3` layout.
- The standard separation is 12 px, with 12 px top spacing from the primary key/value area.
- Increasing card height does not replace this required visual separation.

## Kubernetes Ingress inventory reference

The Ingress Inventory page follows the same resource-inventory baseline as Inventory Overview, Nodes, Namespaces, Workloads, Pods, and Services.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Ingress count, TLS-enabled count, and published-host count are contextual hero metadata and use rectangular brand labels. The aggregate TLS posture is the only semantic label in the hero panel.
- Exposure summary cards use neutral surfaces with violet labels and icons. The primary TLS-coverage card may use a solid dark-violet surface and runtime progress width; gradients are prohibited.
- Ingress table columns are left aligned except the final Details column, which is right aligned. Cluster, namespace, and Ingress class are metadata labels. TLS configuration is a compact semantic status label.
- Filters use sentence case, 44 px controls, 8 px radius, shared surface tokens, and violet focus states. Loading bars use a solid violet fill.
- Expandable Ingress details use 12 px cards, 8 px violet icon surfaces, consistent sans-serif 12 px key/value typography, compact shared labels, and the shared nested-object pattern for hosts, TLS references, finalizers, and empty collections.
- Ingress class, path type, labels, annotations, host declarations, and finalizers are descriptive metadata. TLS presence may use Normal or Warning because it communicates an operational exposure state.
- Backend routes use a left-aligned table with a compact rectangular path-type label. Empty routes, hosts, TLS entries, labels, annotations, and finalizers use the shared dashed violet information state.
- TLS details show Secret references only. Certificate validity, expiry, and governance state remain in Kubernetes TLS Secret Governance; request rate, latency, and error behavior remain in Analytics.

## Kubernetes Storage inventory reference

The Storage Inventory page follows the shared Inventory Overview geometry and interaction standard.

- Use the Inventory Overview hero geometry: `p-5 lg:p-6`, a 7/5 split, `gap-5`, a right panel with `min-h-[13rem]`, compact two-column metrics, and the footer action `Manage Clusters`.
- Storage object count, StorageClass count, and combined PV/PVC count are contextual hero metadata and use rectangular brand labels. Aggregate collection posture is the only semantic label in the hero panel.
- Summary cards use neutral surfaces with violet labels and icons. The primary PV-coverage card may use a solid dark-violet surface and runtime progress width; gradients are prohibited.
- Storage table columns are left aligned except the final Details column, which is right aligned. Cluster, namespace scope, object type, and capacity use compact metadata labels. Binding or lifecycle state uses compact semantic labels.
- Expandable Storage details use the modern Inventory detail surface, 12 px key/value typography, violet non-status iconography, proportional card heights, nested object summaries, and concise bottom tips.
- StorageClass parameters, claim selectors, conditions, associated claims and Pods, labels, and annotations use shared nested or dashed empty-state treatments. Credential and Secret content must never be rendered.
- Declared capacity and binding metadata remain inventory context; filesystem usage, pressure, growth, and recommendations remain in Storage Analysis and Intelligence.

## Kubernetes Configuration inventory reference

The Configuration Inventory page follows the same Inventory Overview baseline while preserving the metadata-only safety boundary.

- Use the shared hero geometry and footer action `Manage Clusters`. ConfigMap count, Secret count, and total object count are contextual metadata labels; the safe metadata posture is the only semantic hero label.
- Summary cards use neutral surfaces and violet iconography. The composition card may use a solid dark-violet surface; gradients are prohibited.
- Configuration table columns are left aligned except Details. Cluster, namespace, object type, and key count use compact metadata labels. Immutable state uses a compact semantic label.
- Do not show payload values or Secret values. Inventory may show object identity, immutable state, key names, and current Pod references only.
- Expandable details use three proportional cards: Object identity, Key metadata, and Used by Pods. Each populated card ends with one concise bottom tip; empty collections use the shared dashed violet state.
- Configuration Inventory remains read-only snapshot context. ConfigMap create, update, and delete workflows remain in Kubernetes Operations, and Secret reveal remains protected by its separate governance controls.

## Kubernetes ConfigMap operations reference

ConfigMap Management follows the KAORI authenticated operations standard while preserving the live Kubernetes API boundary.

- The landing, create, update, and delete heroes use a solid `kaori-primary` surface with `page_hero.intro()`, aligned title/description, rectangular metadata labels, 16 px outer radius, and a right-side boundary panel. Do not use gradients.
- The landing page uses three neutral workflow cards. Create and Update use violet brand actions; Delete uses Critical only for destructive controls. Permission availability is a compact semantic state.
- Create places Target location and Create guardrails side by side with equal height. Update and Delete use the same mirrored structure for Select ConfigMap and their guardrails.
- Main operational sections use 12 px outer card radius, 8 px icon surfaces, neutral surfaces, shared outlines, and violet non-status iconography.
- Form controls use sentence case, 44 px height, 8 px radius, `text-sm`, shared surface/outline tokens, and violet focus rings.
- Live target, key count, and impact context are contextual metrics, not health statuses. Use neutral metric cards. Immutable objects use Warning; destructive consequences and exact-name confirmation use Critical.
- ConfigMap selectors and current values remain live Kubernetes data. Inventory is used only for best-effort consumer context and management counters.
- Entry rows use neutral containers and monospace value fields because users are editing configuration payloads. Add is a violet secondary action; remove is Critical.
- Workflow side panels use a solid dark-violet surface with compact numbered steps. Final action strips keep validation secondary and mutation primary.
- Workload references, diff counts, object types, and other descriptive values use compact rectangular metadata labels rather than pills.


### ConfigMap hero geometry

- ConfigMap Management, Create, View & Update, and Delete use the Inventory Overview hero geometry as the size baseline: `p-5 lg:p-6`, a 7/5 split, `gap-5`, and a right context panel with `min-h-[13rem]`.
- The right panel uses one compact semantic status, two equal metric/context cards, and one footer action. Do not stack three context cards or free-form paragraphs that make the hero taller than Inventory Overview.
- The landing footer action is `Manage Clusters`; child workflows use `ConfigMap Management` as the back action.

## Kubernetes Secret operations reference

Secret Management follows the same authenticated operations geometry as ConfigMap Management while preserving stronger Secret-specific security boundaries.

- Landing, Create, Replace, Protected Reveal, single TLS rotation, and bulk TLS rotation use the Inventory Overview hero baseline: `p-5 lg:p-6`, a 7/5 split, `gap-5`, 16 px hero radius, and a right context panel with `min-h-[13rem]`.
- Right hero panels use one compact semantic status, two equal context cards, and one footer action. Do not use free-form paragraphs that make one Secret workflow hero taller than another.
- Use a solid `kaori-primary` hero and a solid dark-violet workflow panel. Gradients and radial decorations are prohibited.
- Secret workflow cards and forms use 12 px radius, 8 px icon surfaces, neutral cards, shared outlines, and violet non-status iconography.
- Form controls use 44 px height where applicable, 8 px radius, sentence-case labels, `text-sm`, and violet focus rings. Sensitive payload editors may use the elevated neutral surface with monospace text.
- Descriptive Secret types and object metadata use rectangular violet labels. Permission, readiness, approval, expiry, reveal, warning, and destructive states use compact semantic labels.
- Create never overwrites. Replace never reads existing values and patches only entered keys. Protected Reveal preserves step-up, namespace policy, approval, rate-limit, and one-time access boundaries. TLS workflows validate the certificate/private-key pair before mutation.
- Secret payloads are never persisted or included in notifications, audit metadata, hero summaries, result cards, or background task arguments.

### Live Kubernetes lookup notification

- ConfigMap and Secret selectors use one shared warning notification for live Kubernetes lookup failures.
- Use `components/live_lookup_notice.html`; do not render inline red error text or a separate page-specific alert style.
- The standard uses an 8 px radius, Warning border and soft surface, a 28 px icon container, a 12 px semibold title, a 12 px body with 20 px line-height, and 16 px container padding.
- The notification spans the selector workspace below Cluster, Namespace, and object controls when the workspace uses a multi-column grid. It must be rendered by the parent workspace as a dedicated row after every filter; never place it inside the Namespace grid item. For three-column selectors use the compiled `col-span-3` utility, or place the notice outside the filter grid.
- HTMX namespace partials update their dedicated full-width notice container through an out-of-band swap. The partial must not inject a notice before later filter controls in DOM order.
- Never rebuild or package `app/static/css/output.css` from a source tree that does not contain the active KAORI token definitions. A UI that becomes white with black outlines indicates that token utilities such as `bg-kaori-primary`, `bg-surface-card`, and `border-outline-default` were dropped from the compiled artifact.
- Lookup connectivity, authentication, kubeconfig, RBAC, namespace-list, object-list, and object-read failures use this Warning treatment. Destructive operation failures remain governed by their operation-result component.


## Live Kubernetes selector standard

ConfigMap and Secret operation selectors use one consistent live-source pattern:

- The registered cluster selector appears first.
- The live namespace selector appears second.
- A live object selector appears third when the workflow targets an existing ConfigMap or Secret.
- The `Live` indicator uses the shared compact status label.
- When Kubernetes cannot be reached, the namespace selector is disabled and displays `No live namespaces available`.
- Lookup failures use `components/live_lookup_notice.html` and render as one full-width row below every filter in the card.
- A lookup notice must never occupy a filter column or use page-specific warning markup.
- Cards with a bottom guidance footer use a flex-column layout so the footer remains flush with the bottom edge at every content height.


## Kubernetes operation live selectors

- Place the `Live` status label on the final live object field (`ConfigMap name`, `ConfigMap`, or `Secret`), not on a supporting Namespace field unless the workflow has no object-name field.
- A dependent object field stays disabled until its required Namespace is selected and shows `Select namespace first` while disabled.
- Live lookup failures render as one full-width notification below the complete filter row. The filter grid and notification must not share the same column slot.
- Destructive workflow cards use violet structural borders. Critical red is reserved for the final destructive button, confirmation control, and real consequence messaging.
- Informational TLS rotation surfaces use KAORI violet. Semantic warning colors are reserved for real certificate or mutation risk states.

## Kubernetes TLS Secret governance standard

- Governance TLS Secret overview, detail, and bulk update pages use the KAORI violet authenticated-page baseline: solid `bg-kaori-primary` hero, 16 px hero radius, `p-5 lg:p-6`, a 7/5 split, rectangular metadata labels, and a compact posture panel.
- Structural cards, filter areas, expandable details, upload panels, and pagination use shared surface and outline tokens. Decorative blue, cyan, indigo, fuchsia, and gradient treatments are prohibited.
- Non-status icons, labels, buttons, and section accents use KAORI violet. Certificate health, expiry, invalid state, and destructive update consequences retain semantic Normal, Warning, and Critical colors.
- Overview filters use 44 px controls, 8 px radius, sentence-case labels, and violet focus rings. Tables remain left aligned except explicit action columns.
- Cluster, namespace, SAN count, and other descriptive metadata use compact rectangular labels. Status badges remain compact semantic pills.
- Governance provides posture, relationship, and audit context. Certificate/private-key mutation remains delegated to the controlled Kubernetes Operations TLS rotation workflow.

### TLS Secret governance detail-card standard

- Certificate Identity, Subject Alternative Names, Ingress Usage, and Validity Window use the same detail-card anatomy as Kubernetes Inventory details: a structural header, primary content, optional nested object or dashed empty state, 12 px separation, and one concise shared tip pinned at the bottom.
- Use `components/detail_object.html` for nested summaries and empty collections, and `components/inventory_detail_tip.html` for the bottom information tip. Page-specific tip markup is prohibited.
- Empty SAN, Ingress reference, or validity metadata uses the centered dashed violet empty state. Empty operational context is not a Warning unless a real collection or parsing failure occurred.
- Validity Window is structurally violet/neutral. Healthy green is permitted only inside the compact certificate status badge; date cards, remaining-validity surface, icons, borders, and information tips must not use green or teal decoration.
- Every populated detail card keeps the information tip below its content with the shared 12 px separation. Adding card height is not a substitute for this spacing.

## Settings workspace standard

All Settings workspaces use the KAORI Violet Infrastructure visual system. Heroes use the solid primary violet surface, operational context is presented in a right-side posture card where applicable, and primary actions use violet or high-contrast white inside the hero. Main sections use `bg-surface-card`, `border-outline-default`, and `rounded-xl`/`rounded-2xl`; nested information blocks use `bg-surface-subtle` and `rounded-lg`. Form controls use violet focus borders and rings. Text status labels use the global compact rectangular geometry, while semantic green, amber, red, cyan, and slate remain reserved for operational state. Circular geometry remains limited to avatars, state dots, toggles, progress tracks, and decorative hero shapes.

### Settings and Access disclosure hierarchy

- Explanatory workflow panels that help an administrator understand how to complete the current task open by default. Current examples are Identity creation paths, How LDAP provisioning works, and How each provider is used.
- Consequence, credential, and security-boundary panels stay closed by default so the primary form or registry remains visually dominant. Current examples are Reset impact, Authentication boundary, and Credential boundary.
- Native `<details>` and `<summary>` are preferred for these disclosure panels. Use a violet icon surface, shared outline tokens, sentence-case labels, `group-open` chevron rotation, and explicit Details/Collapse text.
- Protected Secret Reveal Protection Posture and Activity Audit Operational Overview use the same overview anatomy as Role & Access Overview: one structural header, four equal metric cells separated by shared outlines, and one lower information strip containing four concise operational boundaries.
- Activity Audit Log workspace tabs are named Retention and Audit Log. Avoid the ambiguous label Snapshot for the primary audit-record workspace.

### Kubernetes integration rollout

The Kubernetes Integration landing and detail workspaces use the same semantic contract as Alertmanager and Prometheus. Violet identifies KAORI navigation, selection, primary actions, metadata, and focus. Readiness, runtime health, compatibility fallback, blocked APIs, and destructive lifecycle actions use the appropriate semantic family. Kubernetes remains authoritative for live resources; KAORI stores canonical connection context, normalized inventory, runtime evidence, correlation, governance, and audit history.


## Global Semantic Color Contract

The semantic palette is a global application contract, not a domain-specific theme.

- Primary Violet (`#7C3AED`, text `#6D28D9`, soft `#F5F3FF`) is reserved for KAORI identity, active navigation, primary actions, focus, and selected state.
- Info uses `#2563EB`, text `#1D4ED8`, soft `#EFF6FF`.
- Normal uses `#059669`, text `#047857`, soft `#ECFDF5`.
- Warning uses `#D97706`, text `#B45309`, soft `#FFFBEB`.
- Critical uses `#DC2626`, text `#B91C1C`, soft `#FEF2F2`.
- Neutral uses `#64748B`, text `#475569`, soft `#F8FAFC`.
- Pending maps to Info, disabled/unknown map to Neutral, and maintenance maps to Warning.
- Compact status and metadata labels are borderless globally. Border-reference colors are reserved for panels, callouts, modal dialogs, inputs, and destructive controls.
- Provider or feature templates must use shared semantic tokens and label macros instead of introducing raw product-specific color classes.

## Global naming convention

All user-facing environment values use full names such as **Development**, **Staging**, **Production**, **Quality Assurance**, and **User Acceptance Testing**. Abbreviations such as `dev`, `stg`, `prod`, `prd`, `qa`, and `uat` are accepted only as legacy input aliases and must never be rendered. The canonical contract is defined in `docs/standards/NAMING_CONVENTIONS.md`.
