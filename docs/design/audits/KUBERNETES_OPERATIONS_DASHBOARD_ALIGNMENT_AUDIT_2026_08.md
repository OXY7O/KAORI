# Kubernetes Operations Dashboard Alignment Audit — August 2026

## Status

Approved as the canonical KAORI operational dashboard reference. No visual redesign is required.

## Scope reviewed

- route and RBAC boundary;
- database and worker-snapshot source contract;
- HTMX section orchestration;
- Hero, scope, KPI, tab, section-card, table, chart, flow, callout, state, and pagination composition;
- light and dark theme ownership;
- responsive behavior;
- accessibility semantics;
- dashboard wording;
- documentation, tests, and quality-gate coverage;
- unused dashboard presentation APIs.

## Approved strengths

- Strong information hierarchy: identity, scope, indicators, peer analysis, interpretation, and action.
- Snapshot-first architecture keeps web requests read-only and avoids provider latency in page rendering.
- Lazy section loading reduces initial query and template work.
- Shared components own all recurring geometry and semantic states.
- Integrated tabs preserve scope and URL state without rendering a second card shell.
- Equal-height peer sections provide balanced operational comparison.
- Cluster Health follows canonical table and pagination rules with page sizes 5/10/25/50.
- Forecast uses the same chart component as Kubernetes Analytics.
- Empty, unavailable, stale, and pending states remain visible instead of collapsing the page.
- Dark mode uses layered neutral surfaces with controlled Violet accents.

## Corrections made without visual redesign

1. Added Arrow Left/Right, Home, and End keyboard navigation to Tab Style 1.
2. Replaced copy that implied live provider queries with snapshot-accurate detailed-signal wording.
3. Made Reporting guidance format-neutral after the PDF/CSV and XLSX/CSV report contract was introduced.
4. Standardized `Alertmanager` product casing in dashboard source copy.
5. Removed unused `tone` and `scope_tone` presentation arguments from the operational KPI card contract.
6. Added a dedicated operational-dashboard verifier and registered it in the static quality gate.
7. Expanded the canonical pattern document so future dashboards can reuse the design without copying page-local styles.

## Technical risks retained for separate work

The repository helpers currently favor graceful rendering by returning empty collections or zero values when a database query raises an exception. This keeps the dashboard available, but a database failure can be visually similar to a legitimate empty dataset. That behavior is outside this visual-preservation change and should be handled later through an explicit repository result contract such as `available/data/error_code`, plus server-side logging and a non-technical unavailable state.

## Final decision

The existing visual design is approved and should be preserved. The Kubernetes Operations Dashboard is the reference implementation for `docs/design/patterns/OPERATIONAL_DASHBOARD.md`. Future operational dashboards should reuse its composition and shared components rather than restyling or duplicating the page.
