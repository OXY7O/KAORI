# KAORI Core Workspace Lock v1

Status: Locked baseline
Date: 2026-08-07

## Locked Scope

This lock applies to the user-facing workspaces that are considered stable before KAORI proceeds to additional product areas:

- Welcome
- Kubernetes Inventory
- Kubernetes Analytics
- Kubernetes Operations
- Kubernetes Governance
- Integrations, including Kubernetes, Prometheus, and Alertmanager provider workspaces

The lock is intentionally narrower than the entire repository. Reports, Intelligence, Settings, Notifications, and Identity remain independently reviewable domains.

## Frozen Visual Contract

The following decisions may not be changed page-by-page:

1. Shared KAORI Violet palette owns identity and interaction emphasis. Semantic green, amber, red, and neutral colors represent state only.
2. Light and dark modes use semantic design tokens. Raw Tailwind color palettes and raw hex colors are forbidden inside locked templates.
3. Visible headings, tabs, filter labels, form labels, table headers, modal titles, and button labels use Title Case. Narrative text stays sentence case. Technical identifiers preserve source casing.
4. `components/table.html` and `components/table_label.html` remain authoritative for canonical tables and compact labels.
5. Compact labels are rectangular `rounded-md`, single-line by default, and use shared semantic/metadata macros. Ordinary repeated state uses a semantic indicator rather than decorative Lucide icons.
6. Default table page size remains 5 with options 5/10/25/50 and canonical resource-aware pagination.
7. Provider detail workspaces use shared Framed Workspace Tabs V2. Page-local tab geometry is forbidden.
8. Inline `style=` and inline DOM event handlers are forbidden in locked templates. Dynamic progress width is owned by `components/progress_bar.html`; dialog behavior is owned by shared JavaScript.
9. Operational toast auto-dismiss and countdown behavior is owned by `app/static/js/operational_toasts.js`.
10. New copied surface shells, compatibility shims, dead wrappers, and reintroduced obsolete paths are release blockers.
11. Kubernetes Topology is canvas-first at every breakpoint. Display Controls and Topology Details are on-demand overlay drawers and must never become persistent columns that reduce the graph working area.

## Frozen Evidence and Security Boundaries

- All-clusters Inventory and Analytics remain committed-snapshot only unless an explicitly selected cluster permits a documented live operation.
- Runtime Health, Validation Readiness, and consumer eligibility are separate evidence dimensions.
- Minimum Kubernetes validation RBAC does not grant cluster-wide Secret reads. Secret value access belongs to the separate governed Operations flow.
- Prometheus/Alertmanager source readiness, binding validation, and effective resolution remain independent evidence.

## Change Policy

A future change to a locked rule requires all of the following in the same commit:

1. explicit design-system documentation update;
2. audit rationale explaining why the frozen rule is changing;
3. affected contract/verifier update;
4. regression test proving the new behavior;
5. no silent baseline increase.

Local visual exceptions without documentation are not accepted.

## Enforcement

The static quality gate runs:

```bash
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_core_workspace_legacy_cleanup.py
python scripts/verify_core_workspace_code_health.py
python scripts/verify_architecture_boundaries.py
python scripts/verify_ui_style.py
python scripts/verify_ui_reuse.py
```

Domain-specific Inventory, Analytics, Operations, Governance, and Integration contract tests remain additional release gates.
