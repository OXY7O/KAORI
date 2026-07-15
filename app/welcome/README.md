# KAORI Welcome

Welcome is the authenticated platform landing page and is not an infrastructure dashboard.

## Product and data boundary

- Every authenticated role can open `/` and `/welcome`; both resolve to `welcome.index`.
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

## Scalability and presentation

- The catalog groups workspaces by operational purpose: visibility, operations, assurance, and platform administration.
- Workspace search operates only on cards already rendered for the current user, so client-side filtering cannot reveal unauthorized destinations.
- Presentation is maintained in `templates/welcome/index.html`, `static/css/welcome.css`, and `static/js/welcome.js`.
- Keep workspace cards compact, consistently structured, and suitable for a growing number of features.
