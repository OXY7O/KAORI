# KAORI Content Tabs

## Purpose

Content Tabs are the canonical compact tab treatment for switching several closely related views inside one already-established workspace surface. They are visually denser than Integrated Workspace Tabs and do not create a second parent workspace hierarchy.

## Registry

- Review label: **Tab Style 4 — Content Tabs**
- Semantic key: `content-tabs`
- Component owner: `app/templates/components/content_tabs.html`
- Primary references: Kubernetes/Object Storage Analytics content workspaces, Alert Intelligence long-form sections, and Protected Secret Reveal.

## When to Use

Use Content Tabs when all views:

- are subordinate content states or sections **inside one established route/page**;
- share one page, scope, and analysis context;
- are subordinate to an existing workspace heading;
- benefit from compact pill-like navigation;
- may have four or more peer content views;
- do not require the stronger page-level hierarchy of Integrated or Framed Workspace Tabs.

Do not use Content Tabs for Sidebar v2.1 route-level level-3 navigation; those peer routes use Integrated Workspace Tabs. Do not use Content Tabs for a full Integration parent workspace or a two-view local visualization toggle. Protected Secret Reveal is an approved security-sensitive exception because it preserves a real URL fallback while adopting the established Analytics visual treatment.

## Geometry

The shared component owns:

- compact `min-h-10` tab controls;
- icon + label composition;
- optional compact user-facing metadata badge;
- active KAORI Violet treatment;
- neutral inactive treatment;
- wrapping by default;
- optional single-row `nowrap` mode with horizontal overflow as the narrow-viewport fallback.
- the same geometry for client-owned buttons and server/URL-owned links.

A dense tabset may use `nowrap=true` only when the labels have already been shortened to concise user-facing vocabulary. Horizontal overflow is the fallback, not a reason to expose internal identifiers or abbreviate labels into unclear acronyms.

## Badge Contract

A badge is optional and must be actual user-facing metadata such as a compact count or posture label.

Never pass an internal section key, snapshot key, DOM target, dataset identifier, or loader mode as a visible badge. Consumers with richer internal tuples must call the component with `show_badges=false` or provide a dedicated display tuple.

## Runtime Ownership

The component owns active/inactive visual class tokens. State ownership depends on the rendering mode.

### Client-owned button mode

`render_buttons()` is for a page controller that owns tab activation. The controller applies the class contract exposed by each rendered tab through:

- `data-kaori-tab-active-classes`;
- `data-kaori-tab-inactive-classes`.

Controllers must not duplicate Tailwind palette/state class lists.

KAORI Analytics uses `app/static/js/analytics/controls.js` as its single tab-state owner across Kubernetes and Object Storage workspaces. Analytics templates must not add a parallel Alpine `activeTab` controller for the same tabset.

The Analytics controller owns:

- click activation;
- Arrow Left/Right, Home, and End keyboard navigation;
- `aria-selected` and roving `tabindex`;
- native `hidden` state for panels;
- optional URL/session persistence;
- one-time lazy HTMX activation through `kaori:analytics-tab-activated`.


### Controlled progressive-link mode

`render_controlled_links()` is the approved mode for Protected Secret Reveal. It reuses the same Content Tabs geometry and active/inactive classes, while the page-owned Alpine controller keeps instant switching, URL synchronization, roving keyboard focus, and panel visibility. Every tab also keeps a real `href` with the server-owned view parameter, so the workspace remains navigable if Alpine is unavailable.

The controlled mode must not duplicate Tailwind state classes in the consuming page. The shared component remains the visual owner; the page owns only the security-sensitive view state and lifecycle.

### Server-owned link mode

`render_links()` is for URL/server-owned section state. It renders real navigation links with `aria-current="page"` for the selected section and may optionally carry shared HTMX navigation controls (`hx-target`, `hx-select`, `hx-swap`, `hx-push-url`, `hx-indicator`, and `hx-sync`). It must not adopt the Analytics button controller or duplicate its ARIA tab-widget behavior.

Server-owned consumers may use `nowrap=true` for concise long-form section labels. This preserves the same Content Tabs geometry while allowing horizontal overflow on narrower viewports. Alert Intelligence is the reference server-owned Intelligence consumer.

## Progressive Fallback

For client-owned `render_buttons()`, the server must render one valid active tab and panel before JavaScript executes. Non-default panels use the native `hidden` attribute. If the controller does not execute, the initial content remains readable rather than producing a blank workspace.

For server-owned `render_links()`, every section link retains a real `href`; HTMX is progressive enhancement only. If HTMX does not execute, normal navigation still resolves the selected server-rendered section.

## Accessibility

Client-owned `render_buttons()` uses the ARIA tab-widget contract:

- wrapper uses `role="tablist"`;
- controls use `role="tab"`;
- each tab has `aria-controls`;
- active tab has `aria-selected="true"` and `tabindex="0"`;
- inactive tabs have `aria-selected="false"` and `tabindex="-1"`;
- panels use `role="tabpanel"` and `aria-labelledby`;
- decorative icons are `aria-hidden="true"`.

Server-owned `render_links()` uses navigation semantics instead: the wrapper is a labelled `<nav>`, the selected link uses `aria-current="page"`, and native link keyboard behavior is preserved. Do not add `role="tab"` to server-owned links.

## Analytics Overview Reference

The reviewed Overview vocabulary is:

`Usage · Capacity · Workload · Storage · Consumers · Forecast · Alerts · Actions · Guidance`

Internal identifiers such as `resource-snapshot`, `capacity-snapshot`, or `top-consumers` are runtime metadata and must never be rendered beside those labels.


## Kubernetes Administration — Secret Reveal

Within the existing **Overview · Secret Reveal** Integrated Workspace Tabs, the Secret Reveal
workspace has two subordinate content views: **Cluster Prerequisites** and **Namespace
Policies**. This is a Content Tabs controller (Tab Style 4), not a second level-3
route navigator, Integration-style framed parent card, or a new tab family.

- Follow the approved Integration domain workspace composition: one shared operational
  shell owns a compact header, the common selected-cluster scope control,
  embedded Content Tabs (`embedded=true`), and a padded active panel. Do not
  render the cluster selector, tab row, and panel as three separate cards, or
  repeat an external Cluster Readiness intro and a second inner card title.
- `render_controlled_links()` owns tab geometry and true full-route `href`
  fallbacks; the page-owned Alpine controller owns instant switching, roving
  Arrow/Home/End, URL `view=prerequisites|policies`, back/forward and panel
  visibility/ARIA. Inactive panels must be hidden from the accessibility tree.
- Cluster switches and readiness/policy mutations preserve the selected view
  through the existing HTMX workspace replacement. Namespace search, filter,
  page size and navigation keep `view=policies`. Initial render must honor the
  URL so no-JavaScript navigation shows only its requested content view.
- Credential/attestation configuration is committed KAORI state; configured
  prerequisites do **not** establish live Kubernetes RBAC or Secret access.
  Only the authorized Secret Reveal execution path performs runtime checks.
- Existing Namespace Policy table/pagination semantics, OOB posture updates,
  CSRF and permission boundaries remain separate authorities.
- **Namespace policy editing** uses the canonical row action to reveal a
  separate full-width companion editor row. The action retains a compact
  **Edit Policy** label, shared action geometry, and accessible `aria-controls`
  and `aria-expanded` state. The editor preserves a single-row editing
  boundary, stable default row heights, and a labeled policy selector with
  neutral **Cancel** / **Save Policy** actions. The companion row is
  **server-hidden by default** with the existing `hidden` utility class,
  and shared `detail_rows.js` (`data-detail-toggle`/`data-detail-group`)
  owns exclusive open/close, ARIA state and HTMX-safe delegated events. Do not
  use Alpine `x-show` on table rows for this pattern. Cancel follows a safe
  GET of the current filtered page, restoring the read-only table without
  policy mutation. Keyboard and browser behavior still require UAT.
- **Live Source** provenance and manual **Refresh** belong to a standalone
  full-width utility card above Namespace Policies. Include source authority,
  selected cluster, truthfully sourced status and last refresh (or absence
  of one); do not repeat its status in table columns.
- Canonical **Clear Filters** is not a permanent header action: it stays
  hidden until the Namespace search or policy filter is active. The shared
  `registry_ui.clear_filters_action()` remains the interaction owner.
  Client-side filter state updates its visibility while table-only HTMX
  updates preserve the search field; initial server rendering preserves
  the hidden state when scripting is unavailable.
- Namespace Policies renders its header via the approved
  `table_ui.inventory_block_header()` macro, which owns the shared
  `components/loading_bar.html` indicator **inside the block header below
  its title/action row**. This reuses the Activity Audit Table pattern
  instead of page-local `loading_bar_classes()` or always-visible tracks.
  The indicator is hidden when idle and shows only during HTMX requests.
- The table and companion editor use available horizontal space to explain
  live Namespace state and configured reveal policy. The editor shows
  namespace, current policy, proposed policy, eligibility context and compact
  Cancel/Save actions without a second nested card.
- This is a presentation-only refinement. Existing CSRF, readiness and
  live-state option restrictions, HTMX mutation/update, and audit/security
  authorities remain unchanged.

## Review Checklist

- Uses `components/content_tabs.html` directly.
- No domain compatibility wrapper exists.
- Chooses `render_buttons()` for client-owned state or `render_links()` for URL/server-owned state.
- One state owner only.
- Shared component owns active/inactive visual classes.
- Internal identifiers are not visible badges.
- Initial panel is server-readable without JavaScript.
- Keyboard and ARIA contracts are intact.
- Dense one-row mode remains readable at the 14-inch target viewport and scrolls rather than wraps on narrower viewports.
