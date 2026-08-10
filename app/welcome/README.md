# KAORI Welcome

Welcome is the authenticated platform landing page and is not an infrastructure dashboard.

## Product and data boundary

- Every authenticated role can open `/` and `/welcome`; both resolve to `welcome.index`.
- `/` is a canonical Welcome route, not a redirect or compatibility alias to the retired dashboard package.
- Welcome describes KAORI as an extensible infrastructure operations platform. It must not define KAORI through the technologies currently integrated.
- Welcome must not load live Prometheus, Alertmanager, Kubernetes, Server, HCI, storage, or other infrastructure data.
- Asset-specific KPI, capacity, alert, and inventory aggregation belongs in the relevant dashboard or domain page.

## Role-aware workspace catalog

- Workspace definitions are maintained in `shortcuts.py`.
- Each workspace must declare an operational capability group, functional label, infrastructure scope, icon, description, and one or more permission-to-endpoint targets.
- A workspace is rendered only when the signed-in user has at least one declared permission target. A target with `None` is permitted for every authenticated user and should be used only for genuinely universal destinations such as the personal account page.
- Permission checks in Welcome control discoverability only. Every target route and protected action must continue to enforce authorization on the server side.
- Empty capability groups are not rendered. This prevents headings or counts from exposing inaccessible features.
- New integrations should extend existing capability groups where possible instead of creating product-specific global navigation categories.

## Presentation contract

- `templates/welcome/index.html` composes the canonical hero, catalog toolbar, capability groups, shared workspace cards, and shared empty state.
- `templates/components/welcome_capability_group.html` owns the Welcome-specific dark Violet category anchor. Do not recreate its geometry in the page template.
- `templates/components/workspace_link_card.html` owns reusable destination-card geometry and scope metadata.
- `static/js/welcome.js` only filters already-authorized rendered cards and synchronizes visible counts.
- `docs/design/patterns/WELCOME_WORKSPACE_CATALOG.md` is the canonical layout and interaction pattern.
- Do not add a Welcome-specific CSS file or inline style bundle. Use semantic Tailwind tokens and shared components.

## Scalability

- The catalog groups workspaces by operational purpose: visibility, operations, assurance, and platform administration.
- Workspace search operates only on cards already rendered for the current user, so client-side filtering cannot reveal unauthorized destinations.
- Keep workspace descriptions concise and suitable for a growing number of features.
- Do not add pagination while the grouped catalog remains compact. Any future server-driven pagination must use the shared pagination component.
## Test strategy

Welcome uses the layered KAORI release strategy:

- **Static Quality** — canonical lint/format/type/architecture/source-hygiene gates.
- **Contract Test** — `tests/contracts/welcome/test_welcome_navigation_contract.py`.
- **Unit Test** — `tests/unit/welcome/test_welcome_target_resolution.py` proves deterministic first-authorized/universal/no-match target policy independently from Flask request state.
- **Functional Test** — `tests/welcome/test_welcome_characterization.py`.
- **Integration Test** — `N/A`: provider/database integration is intentionally absent from the Welcome product boundary. Database/provider behavior belongs to the Integration layer when a reviewed domain actually owns that boundary.
- **Security Regression** — `tests/security/welcome/test_welcome_security.py`.
- **Rendering/UI Contract** — `tests/rendering/welcome/test_welcome_rendering.py`.
- **End-to-End Smoke** — `tests/e2e/welcome/test_welcome_smoke.py`, using the real Flask application, routing, session, Flask-Login, shared layout, and application shell while isolating external persistence/provider dependencies so the smoke remains deterministic in local and CI runs.
- **Migration Test** — `tests/migrations/test_retire_welcome_view_permission.py` protects retirement of the non-enforcing legacy permission.

## Release evidence

- `scripts/verify_welcome_final_lock.py` is the canonical Welcome release verifier and must be called directly by `scripts/quality_gate.sh`.
- `tests/welcome/test_welcome_characterization.py` is permanent behavioral evidence for permission-filtered discoverability, universal Settings access, first-authorized target resolution, and multi-permission deduplication.
- `tests/contracts/welcome/test_welcome_navigation_contract.py` remains supporting structural/UI evidence; it must not be the only Welcome test.
- `scripts/verify_feature_test_coverage.py` requires Welcome functional, security, rendering, and E2E evidence after this final recheck.
- `welcome.view` must not return to `DEFAULT_PERMISSIONS`; authentication, not a synthetic permission, owns Welcome admission.

