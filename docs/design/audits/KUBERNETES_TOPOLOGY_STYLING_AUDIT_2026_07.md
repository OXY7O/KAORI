# Kubernetes Topology Styling Audit — July 2026

## Decision

Approved package:

- A1 — Visualization Workspace Style 1: Adaptive Explorer;
- B — Tab Style 3: Compact Segmented Tabs;
- C1 — Graph plus accessible Resource List;
- D1 — Tokenized five-domain topology palette.

## Problems Removed

- duplicate sync/source information in the hero;
- persistent narrow three-pane layout on 14-inch laptops;
- five unrelated header actions;
- page-local loading bar geometry;
- raw per-resource and edge hex colors in JavaScript;
- bordered status legend labels;
- relationship semantics represented as status badges;
- long Tailwind-heavy inspector HTML strings generated in JavaScript;
- `role="application"` without complete graph keyboard navigation;
- graph-only access when the renderer fails;
- unconditional loading of every inventory family for every scope/depth;
- nested all-Service/all-Pod selector matching.

## Reusable Owners

- `components/visualization_workspace.html`
- `components/segmented_tabs.html`
- `inventory/topology/partials/_inspector_templates.html`
- `frontend/styles.css` topology tokens

## Reference Behavior

At `2xl`, controls, graph/list, and inspector are persistent. Below `2xl`, the canvas remains primary while Controls and Details use adaptive drawers.

Tab Style 3 switches Graph/Resource List and Details/Relationships. Resource List, search, JSON export, and payload-based detail inspection remain available if Cytoscape is unavailable.

## Performance Contract

Topology payload cache key includes the committed generation signature and normalized filters. Scope/depth prevent unnecessary model queries. Service selector matching only scans Pods in the same cluster and namespace.

## Validation Targets

- zero raw hex values in `app/static/js/inventory/topology.js`;
- no page-local arbitrary font sizes in Topology hero/workspace/inspector templates;
- no page-local `role="tablist"` outside shared tab components;
- no inline style in Topology templates;
- Jinja parse, JavaScript syntax, Python compile, style guardrails, and Topology contract tests pass.

## Readable Graph Node Refinement

The canonical graph uses compact rounded domain badges with one-line external object-name labels, bounded ellipsis, and a semantic status dot. Full names and resource types remain available through Resource List and Details. Containment lines are quiet dashed orthogonal connectors without arrowheads; dependency labels remain progressive-disclosure content.
