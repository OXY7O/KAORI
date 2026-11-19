# KAORI Navbar and Application Shell Standard v1.0

This document owns the authenticated top-navbar interaction contract.

Canonical implementation:

```text
app/templates/components/navigation/navbar.html
app/templates/components/navigation/_notification_center.html
app/static/js/navbar.js
app/templates/layouts/app.html
```

Canonical enforcement:

```text
scripts/verify_application_shell_standard.py
scripts/verify_javascript_syntax.py
tests/contracts/design/test_application_shell_interaction_contract.py
```

## Scope

The global navbar owns:

- sidebar collapse/expand control;
- breadcrumb/current-page context;
- Quick Actions;
- Notification Deck;
- Account menu.

These are application-shell utilities. Domain pages must not create parallel implementations.

## Desktop sidebar toggle icon states

The desktop navigation toggle uses canonical Lucide panel glyphs, not bare
chevrons. Its visual arrow indicates the **next action** while the panel outline
remains consistent with the approved Violet application shell:

- **Expanded sidebar (250 px):** `panel-right-open` — right divider and
  left-pointing arrow, matching the accepted operator reference, indicates
  **Collapse navigation**.
- **Collapsed sidebar (78 px):** `panel-right-close` — the same outline
  with a right-pointing arrow indicates **Expand navigation**.

The existing `sidebarExpanded` state controls which glyph is visible,
`aria-expanded`, accessible label/title, and local-storage persistence.
The separate mobile off-canvas `menu` trigger is unchanged. Keep the existing
40 px toggle target and light/dark hover/focus treatment.

## Alpine ownership

Navbar state and notification refresh behavior are owned by the named Alpine component `kaoriNavbar` in `app/static/js/navbar.js`.

The template uses only:

```html
x-data="kaoriNavbar"
```

Do not place a multi-method JavaScript object literal directly in the `x-data` attribute. Complex inline Alpine programs are prohibited because HTML/Jinja formatting can remove statement boundaries and make the whole navbar fail to initialize.

`navbar.js` must load before `alpine.min.js` so the `alpine:init` listener can register the component before Alpine initializes the page.

## Exclusive menu state

Only one navbar utility surface is open at a time:

- opening Quick Actions closes Notification Deck and Account;
- opening Notification Deck closes Quick Actions and Account;
- opening Account closes Quick Actions and Notification Deck;
- Escape closes all three.

Quick Actions and Account are anchored dropdowns. Notification Deck is the canonical right-side overlay/drawer surface.

## Quick Actions: queue versus open

The authenticated navbar's **Quick Actions** dropdown is a compact, anchored
Violet shell utility, not a second workflow navigation system. Each entry
retains its authorized destination, interaction semantics, and evidence owner:

- **QUEUE** marks **Sync All Inventory**, an authorized CSRF-protected POST
  that enqueues eligible managed-domain inventory jobs. Keep HTMX double-submit
  protection and the existing operational feedback contract.
- **OPEN** marks **Generate Report**, **Jobs & Executions**, and **Alert
  Center**. These are ordinary navigation links to their existing governed
  workspaces; opening a report form must not imply that a report was generated.

Use concise sentence-case descriptions, compact shared shell spacing, semantic
Violet chips, and distinct queue-action versus navigation icons. Preserve
keyboard focus, exclusive dropdown state, Escape/outside-click behavior,
responsive anchoring, light/dark tokens, and RBAC filtering. Do not introduce
new page-local cards or an ungoverned action dispatcher.

## Notification refresh

Notification Deck snapshot refresh:

- uses same-origin credentials;
- requests JSON only;
- has a five-second abort timeout;
- avoids overlapping requests;
- queues one follow-up refresh when a request is already running;
- updates active/unread badges and reprocesses HTMX content;
- reports connection problems through UI state rather than breaking shell interaction.

A refresh failure must not disable Quick Actions or Account.

## Accessibility

- icon-only controls require `aria-label`;
- expandable controls expose `aria-expanded`;
- Notification Deck exposes dialog semantics;
- Escape closes active shell surfaces;
- all interactive controls retain visible keyboard focus;
- decorative icons do not carry the accessible name.

## JavaScript quality gate

Every first-party file under `app/static/js/`, `frontend/**/*.js`, and `scripts/**/*.mjs` must parse with Node's syntax checker. Prettier remains the formatting authority. The shell verifier additionally rejects a complex inline navbar `x-data` implementation.

## Application-shell top boundary

The authenticated application shell owns one vertical scrollport:

```text
navbar / breadcrumb context
↓
main[data-kaori-main-scroll]
↓
page content inset
```

The main scroll owner must preserve the same top scroll-padding as the page-content inset:

- default: `scroll-pt-5`;
- `lg`: `scroll-pt-6`;
- `2xl`: `scroll-pt-7`.

This protects fragment navigation, `scrollIntoView()`, HTMX/history-driven focus targets, and other programmatic scroll alignment from colliding with the top edge of the application content viewport.

Do not compensate with page-local `mt-*`, inline offsets, or domain-specific spacer elements. The shared shell owns this boundary.


## Global Search capability discovery

The authenticated **Search KAORI** overlay uses the existing
`components/navigation/_global_search.html` dialog and `kaoriNavbar` controller.
Its read-only `/search/global` response has two deliberately separate sources:

- **Navigation and Quick Navigation:** authorized two-level workspace/capability
  destinations from `app/common/workspace_navigation.py::build_sidebar_navigation`.
  This is the same server-side source as the current sidebar; Source Control's
  local-administrator eligibility and each capability's permission filtering
  must be applied **before** results are assembled. Empty-query Quick Navigation
  is a bounded curated subset of these actual visible destinations. Legacy
  deep-page aliases may supplement typed queries, but duplicate URLs are removed.
  Providers and registered instances remain within their owning capabilities.
- **Resources:** the existing committed Kubernetes Cluster/Inventory and
  Object Storage System/Bucket records only, with permission checks, minimum
  two-character query, bounded results and no live external provider query.
  New feature navigation does **not** imply its underlying records are indexed.

Keep keyboard search/arrow/Enter/Escape, focus trapping and return, 180 ms
debounce, abortable reads, no-store, source-bound empty/loading/error states,
accessibility, Violet and responsive geometry unchanged. Updating an implemented
sidebar capability should make that capability discoverable through Search
without adding another hard-coded list of navigation routes.

A global navigation result must point to a URL buildable without unknown record
identifiers. In particular, `artifact_registry.security_cve_impact` requires a
real `cve_id`: search terms such as `cve` or `impact` navigate to the
permissioned Artifact Registry **Vulnerabilities** inventory, where a committed
finding can link to its exact CVE Impact evidence. Never invent a default CVE.
If a historical navigation alias cannot be built, exclude that item with
an application warning instead of returning HTTP 500 for the whole search.

Broader cross-domain committed-resource indexing requires separate authorization,
evidence/read-model ownership and tests; do not treat a provider's live search API
as KAORI's normal operational index.
