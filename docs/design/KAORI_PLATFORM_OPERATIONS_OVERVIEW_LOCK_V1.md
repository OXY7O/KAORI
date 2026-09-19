# KAORI Platform Operations Overview Final Lock v1

Status: Final Lock  
Date: 2026-08-08

## Purpose

Platform Operations Overview is the read-only landing page for KAORI's cross-cutting operational control plane. It summarizes posture without becoming a second source of truth for Jobs & Executions, Data Lifecycle, or Kubernetes Administration.

## Locked information architecture

The Platform Operations sidebar order is:

1. Overview
2. Jobs & Executions
3. Data Lifecycle
4. Kubernetes Administration

The canonical route is `/platform-operations/` and the canonical endpoint is `platform_operations.overview.index`.

## Locked page structure

1. KAORI violet hero with Platform Operations context.
2. Operational Posture section with one permission-scoped card per available workspace.
3. Control Plane Boundaries section explaining authoritative ownership.

The Overview does not use page-local tabs, forms, mutation controls, or duplicate execution/history tables.

## Permission contract

The Overview is available when the user has at least one of:

- `jobs.view`
- `platform_operations.view_data_lifecycle`
- `kubernetes_secrets.manage_reveal`

Only workspaces covered by the user's permissions are summarized. Hidden domains do not contribute counts or posture.

## Projection contract

- Jobs & Executions posture reuses `build_job_execution_status_context()`.
- Data Lifecycle exposes a DB-only `build_data_lifecycle_overview_summary()` projection.
- Kubernetes Administration exposes a shared `build_kubernetes_administration_summary()` projection.
- Overview composition lives in `app/platform_operations/overview/`.

The landing page must not perform live Kubernetes API calls, Celery topology inspection, archive storage probes, retention previews, or mutation-side validation.

## Status semantics

Each workspace owns its compact status:

- Jobs: bounded Needs Attention, Active, or Ready.
- Data Lifecycle: recent archive failure, active work, enabled-policy readiness, or Policies Disabled.
- Kubernetes Administration: No Clusters, Global Gate Disabled, Readiness Review, or Ready.

The hero summary counts workspaces requiring review rather than summing overlapping domain event counts.

## Ownership boundaries

- Jobs & Executions owns canonical runtime execution, retries, cancellation, result references, queue state, and worker evidence.
- Data Lifecycle owns retention intent, archive evidence, and safe cleanup boundaries while the shared retention engine remains under `app/platform_operations/data_lifecycle/retention/`.
- Kubernetes Administration owns advanced setup/policy boundaries; live Secret value access remains owned by Secret Management.

## UI standard

- Shared `page_hero.html` is mandatory.
- Shared `operational_section_card.html` is mandatory for overview sections.
- Semantic status labels use `table_label.status_indicator_label()`.
- Actions are navigation-only and use the shared section-link button.
- Semantic surfaces must remain dark-mode safe and no raw palette utilities are introduced.
- The page is responsive and does not assume all three workspaces are visible.

## Change control

Any change that adds mutation behavior, live external probes, duplicate execution state, hidden-permission counts, page-local tabs, or a new Platform Operations workspace requires a new Overview lock revision and audit.
