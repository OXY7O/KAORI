# KAORI Platform Operations Final Lock v1.8 Audit — 2026-08-08

## Decision

Platform Operations now owns three stable operational control planes: Jobs & Executions, Data Lifecycle, and Kubernetes Administration. Data Lifecycle has been cut over at code, URL, RBAC, navigation, presentation, and documentation layers rather than moved as a sidebar-only feature.

## Verified Boundaries

- Jobs & Executions remains the canonical JobExecution runtime surface.
- Data Lifecycle owns retention intent, archive storage posture, verified archive evidence, and cleanup controls.
- `app/platform_operations/data_lifecycle/retention` remains the shared archive-first engine used by web, CLI, scheduler, and workers.
- Data Lifecycle permissions are classified under Platform Operations while preserving existing role assignments through migration.
- Settings retains redirect-only compatibility for the former URL and no longer owns lifecycle templates or mutation code.
- Platform Operations navigation order is Jobs & Executions → Data Lifecycle → Kubernetes Administration.
- Shared tabs, Title Case, dark mode, pagination, and semantic-surface standards are enforced.
- Secret Reveal v1.7 behavior is unchanged.
