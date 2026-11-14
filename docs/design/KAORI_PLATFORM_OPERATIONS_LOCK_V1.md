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
- **Execution Overview** owns the single canonical title-adjacent **Guide** for Active Work, Registry and Queues, positioned immediately after the live `Work Active / Queues Clear` posture label. Per-tab content headers retain visible titles and source-backed badges but do not duplicate Guides. The Guide is a sibling of `#execution-overview-posture`, never a child: HTMX OOB status refresh replaces only that status span and must not remove the Guide. Each tab's original guidance remains discoverable from the consolidated Guide, including cancellation permission, committed execution evidence and demand-loaded Celery readiness limits.
- Registry filters submit through HTMX change events and keep URL state.
- **Job Configuration neutral header contract:** all registered Job Configurations reuse the selected-job overview header from `_job_overview.html` and the scheduled/manual header from `_schedule_policy.html`. These large horizontal title/header surfaces use canonical `bg-surface-card` with `border-outline-subtle` (white on light mode, semantic dark surface in dark mode), **not** broad `bg-kaori-soft` or `bg-surface-hover` tints. Only the small identity/icon tiles remain Violet Soft, preserving contrast and hierarchy against semantic Enabled/Disabled badges and actions. The special guarded recovery headers in Artifact Registry and Object Storage use the same neutral background, while keeping their amber warning icon/text and fail-closed confirmation safeguards. This is presentation-only; selected catalog rows, policy toggle cards, execution interval controls, timeline, footer guidance, RBAC and provider authority remain unchanged.
- **Current Execution idle-state alignment:** every registered Job Configuration reuses `_execution_activity.html`. When a job has **no active execution**, the card uses flexible text width plus a right-aligned, content-sized `Ready for Execution` status, rather than reserving half of the desktop card for the badge. Keep the title and helper as separate **single-line desktop** strings when space allows, with the full text available in semantic DOM/title attributes; allow natural wrap on small screens. Do not force mobile nowrap or discard blocked/disabled explanations. When a job **is active**, retain the established dual-column progress/evidence layout, worker process/detail and canonical progress bar. Neither state changes job execution, queue authority, polling, audit or permission checks.
- **Execution & Recent Activity contextual Guide:** the shared `_execution_activity.html` section owns one title-adjacent `info_tip.render(..., variant='guide')` explaining current/read-only state, canonical worker progress and permission-gated manual execution. This is separate from the selected job's safety Guide in `_job_overview.html`; do not duplicate the safety Guide or hide blocking warnings. The section summary, idle state title and compact idle helper target independent one-line desktop rows with full source text exposed through `title` attributes and natural mobile wrapping. Short copy is presentation only; the complete blocked/eligible meaning and live authority stay in their existing state and blocker controls.
- **Formatter-safe dynamic grid:** `_execution_activity.html` selects `current_execution_grid` in a Jinja `set` branch, not as a nested inline expression in the HTML class attribute. The active grid keeps `xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.95fr)]`, and idle uses `lg:grid-cols-[minmax(0,1fr)_auto]`. The underscore separators must remain intact through `djlint` and existing Tailwind compilation; never accept a whitespace insertion in these utility tokens.
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
