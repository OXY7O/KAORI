# KAORI Platform Operations — Data Lifecycle Final Lock Audit — 2026-08-08

## Decision

Data Lifecycle is moved from Settings to Platform Operations as an ownership refactor, not a navigation-only change. The archive-first engine remains shared under `app/retention`, while HTTP orchestration and UI ownership move to a dedicated Platform Operations package. Jobs & Executions remains the canonical runtime evidence surface.

## Audit Findings Resolved

1. **Settings ownership mismatch** — routes, templates, navigation, breadcrumbs, notification links, and runtime-history links previously pointed to Settings.
2. **RBAC namespace mismatch** — lifecycle permissions were classified under `settings.*`; they are renamed in place to `platform_operations.*` so existing role assignments survive the cutover.
3. **Route concentration** — the old route module mixed request parsing, mutation business logic, feedback creation, canonical-job dispatch, archive verification, download handling, and rendering. The new package separates `routes.py`, `service.py`, and `presentation.py`.
4. **Page-local tab debt** — the old Data Lifecycle page owned custom tabs and a hardcoded `bg-white` inactive state. The final workspace uses shared Framed Workspace Tabs and semantic surfaces.
5. **Roadmap placeholder debt** — Planned Domains were displayed before adapters existed. The final page shows only registered, operational domains.
6. **Execution ownership ambiguity** — `Execution History` could be read as a second job registry. The workspace is renamed `Archive History`; worker runtime remains under Jobs & Executions and manual lifecycle notifications link there.
7. **Pagination consistency** — Archive History now uses Title Case `Archive/Archives`, visible `Rows`, and `Rows Per Page` accessibility copy.
8. **Documentation drift** — retention tasks, Activity Audit, integration runtime history, Platform Operations documentation, Settings compatibility documentation, and system information now identify Platform Operations as the owner.

## Verified Boundaries

- Canonical URL: `/platform-operations/data-lifecycle/`.
- Legacy Settings URL is redirect-only compatibility.
- No duplicate lifecycle templates remain under `app/templates/settings/`.
- New Platform Operations package owns route/service/presentation boundaries.
- Shared `app/retention/` engine remains reusable by CLI and workers.
- No direct `.delay()`/`.apply_async()` execution path was introduced.
- Archive-first checksum verification still gates cleanup.
- Role mappings are preserved by permission-row rename migration.
- Dark mode uses semantic surfaces and shared tabs.
- Data Lifecycle is ordered after Jobs & Executions in Platform Operations navigation.
