# Welcome Workspace Catalog Pattern

## Purpose

The Welcome page is a role-aware product landing page. It helps users choose an authorized KAORI workspace without behaving like an infrastructure dashboard.

## Required structure

```text
Canonical Hero
Catalog Header and Search
Visible Result Metadata
Capability Groups
Shared Empty State
```

## Catalog header

- use one metadata label: `Workspace Catalog`;
- use one section title: `Choose a Workspace`;
- keep the description to one sentence;
- keep only the visible result count as inline metadata; role/access identity belongs to the Hero;
- do not add a separate tinted summary strip;
- search uses the standard 40 px form control and `rounded-lg` geometry.

## Capability group

`components/welcome_capability_group.html` owns the Welcome-specific group layout.

A capability group uses the exact shared Hero surface (`.kaori-hero-shell`) for its Violet anchor, including the canonical dark-mode Hero gradient. This is a deliberate Welcome-only orientation pattern: the surface is visually identical to the Hero but remains smaller, content-light, and action-free so it does not compete with the page Hero.

The anchor contains:

- one icon;
- one action-oriented eyebrow;
- one group title;
- one concise description;
- one visible workspace count.

The anchor does not contain decorative rings, decorative stars, gradients, heavy shadows, or unrelated actions.

## Workspace cards

Every destination uses `components/workspace_link_card.html`. Scope is contextual metadata and therefore uses `table_label.metadata_label(...)`, not a status label or pill.

Cards do not translate vertically on hover. Border, restrained shadow, and icon treatment provide the interactive response.

## Search and authorization

Search operates only on workspaces rendered after server-side permission checks. Empty groups are hidden after filtering. Search must never reveal unavailable workspaces or permission names.

## Pagination decision

Do not paginate the current Welcome catalog. Add pagination only when the catalog becomes server-driven or too large to scan after grouping and search. Any future pagination must use `components/pagination.html`.

## Responsive behavior

- capability anchor appears before its workspace cards;
- desktop uses a fixed category anchor and flexible card grid;
- smaller screens stack the anchor above the cards;
- semantic reading order is unchanged.
## Security boundary

- `/` and `/welcome` require an authenticated session.
- Welcome permission checks control discoverability only; destination routes remain authoritative for authorization.
- The browser receives only workspace cards already authorized by the server. Search must never fetch capability data or permission metadata.
- A `None` permission target is allowed only for a genuinely universal authenticated destination; the current exception is personal Settings (`settings.account`).
- Welcome must remain provider-free: no Kubernetes, Prometheus, Alertmanager, database repository, or worker query is allowed in the landing request.

## Accessibility and keyboard contract

- the workspace search has an accessible label even though the visible UI uses a placeholder;
- visible result counts use polite live-region semantics;
- workspace cards expose a descriptive accessible name and visible `focus-visible` treatment;
- `/` focuses search only when the user is not already editing a text control;
- `Escape` clears the active search, restores all authorized cards, and releases focus;
- hiding a filtered capability group must not reorder the remaining semantic reading order.

## Release evidence

The final Welcome release boundary is protected by:

```text
scripts/verify_welcome_final_lock.py
tests/contracts/welcome/test_welcome_navigation_contract.py
tests/welcome/test_welcome_characterization.py
tests/security/welcome/test_welcome_security.py
tests/rendering/welcome/test_welcome_rendering.py
tests/e2e/welcome/test_welcome_smoke.py
tests/migrations/test_retire_welcome_view_permission.py
```

The canonical quality gate runs the Welcome verifier directly, executes permanent behavioral/security/rendering evidence, and runs E2E smoke as a separate test phase. `welcome.view` is retired because authenticated session admission is the actual Welcome boundary.



## Workspace ownership refinement

Integrations remains a standalone Welcome workspace because it is an independent root menu. It is grouped with **Platform Operations** under the `Act / Infrastructure Operations` capability area, while provider/domain navigation remains inside the Integrations workspace. The Platform Operations card must not inherit `settings.manage_integrations`; each workspace is discovered only through its own authorization boundary.

## Cross-domain visibility workspaces

Inventory and Analytics cards are permission-owned by their asset domain. Kubernetes permissions must not implicitly reveal Object Storage workspaces.

```text
Kubernetes Inventory      → inventory.view
Object Storage Inventory  → object_storage_inventory.view
Kubernetes Analytics      → analytics.view
Object Storage Analytics  → object_storage_analytics.view
```

Object Storage Inventory and Analytics use the `Storage` scope and live in `Understand / Visibility & Operational Insight`. They remain separate workspaces because committed inventory and operational analytics have different evidence boundaries and authorization contracts.
