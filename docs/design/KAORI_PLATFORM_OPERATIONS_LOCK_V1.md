# KAORI Platform Operations Lock v1

Status: Locked canonical baseline
Date: 2026-08-08

## Scope

This lock covers the complete Platform Operations workspace:

- Kubernetes Administration
  - Overview
  - Protected Secret Reveal
  - Cluster Readiness
  - Namespace Reveal Policies
- Jobs & Executions
  - Execution Overview
  - Active Work
  - Execution Registry
  - Queue Activity
  - Job Configuration
  - Current Execution
  - Policy & Configuration

The lock freezes presentation and interaction contracts. Backend behavior may evolve when a documented operational requirement changes, but a page-local visual workaround is not permitted.

## Frozen KAORI Presentation Contract

1. All user-facing headings, table headers, compact metadata headings, and form labels use Title Case. Uppercase utility styling is not allowed in Platform Operations templates.
2. Kubernetes Administration and Jobs & Executions use the shared KAORI workspace-tab components. Page-local `role="tablist"` markup is prohibited.
3. Workspace tabs must remain keyboard operable with Arrow Left/Right, Home, and End behavior and must preserve URL-backed state.
4. Execution Registry uses the shared KAORI loading, filter, action, status, and pagination primitives. Filtering and page-size updates are HTMX-owned; inline DOM event handlers are prohibited.
5. Execution Registry keeps default page size 5 with 5/10/25/50 options and resource-aware pagination.
6. Namespace Reveal Policies must not force a desktop `min-width`/horizontal-scroll table. The table remains four-column and proportional at normal laptop widths.
7. Secret Reveal is a protected operational workflow. Global feature enablement, namespace policy, user permission, step-up/approval requirements, and Kubernetes RBAC remain independent authorization boundaries.
8. Semantic green/amber/red is reserved for operational state. KAORI Violet remains identity, selection, metadata, and primary-action emphasis.
9. Jobs status presentation is owned by the global `components/table_label.html`; Jobs templates must not depend on Integration-specific status components.
10. Raw Tailwind palettes, raw hex colors, arbitrary text sizes, inline styles, inline DOM handlers, page-local tablists, copied canonical surface shells, and page-local semantic border bundles are release blockers in locked Platform Operations templates.
11. Repeated operational card geometry is owned by `components/operational_section_card.html`; semantic border/surface bundles are owned by `components/operational_callout.html`. Platform Operations carries no accepted UI-style debt baseline entries.

## Frozen Interaction Contract

### Kubernetes Administration

- `Overview` and `Secret Reveal` use shared Framed Workspace Tabs.
- Selecting Secret Reveal may lazily hydrate its workspace through HTMX.
- Namespace filter/pagination context is preserved through HTMX requests.
- Namespace policy mutation stays explicit and auditable; no automatic policy mutation is introduced by filtering or navigation.

### Jobs & Executions

- Top-level `Executions` and `Job Configuration` use shared Framed Workspace Tabs.
- `Active Work`, `Registry`, and `Queues` use shared Integrated Workspace Tabs.
- Live job counts may update out-of-band without replacing local tab geometry.
- Registry filters submit through HTMX change events and keep URL state.
- Manual and scheduled execution use the same canonical JobExecution lifecycle and queue ownership.

## Legacy / Dead-Code Lock

The old page-local Kubernetes Administration tab component is obsolete and must remain absent:

```text
app/templates/platform_operations/kubernetes/_tabs.html
```

It is registered in `scripts/cleanup_obsolete_files.sh` and checked by the final-lock verifier.

Existing previously removed Jobs hero compatibility partials also remain obsolete:

```text
app/templates/platform_operations/jobs/executions/partials/_hero_context_metrics.html
app/templates/platform_operations/jobs/executions/partials/_hero_metadata.html
```

## Enforcement

The release gate runs:

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
pytest -q tests/contracts/jobs
```

Any intentional change to this lock requires documentation, verifier/contract updates, and an explicit design rationale in the same commit.
