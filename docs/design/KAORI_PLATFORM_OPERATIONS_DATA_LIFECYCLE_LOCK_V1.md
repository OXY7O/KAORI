# KAORI Platform Operations — Data Lifecycle Final Lock v1

Status: Final Lock
Date: 2026-08-08
Owner: Platform Operations

## Scope

Data Lifecycle is the canonical cross-domain operational control plane for retention intent, verified archive storage, archive evidence, and safe cleanup. This lock moves ownership out of Settings without duplicating the archive-first engine or the canonical job runtime.

## Information Architecture

```text
Platform Operations
├── Jobs & Executions
├── Data Lifecycle
│   ├── Retention Policies
│   ├── Archive Storage
│   └── Archive History
└── Kubernetes Administration
```

`Data Lifecycle` appears immediately after `Jobs & Executions`. Settings does not expose Data Lifecycle as a submenu.

## Code Ownership

- `app/platform_operations/data_lifecycle/` owns routes, operator mutation orchestration, feedback, and workspace presentation.
- `app/templates/platform_operations/data_lifecycle/` owns the UI.
- `app/retention/` remains the domain-neutral lifecycle engine, adapters, archive writer, verification, cleanup safety, lock, task, and policy persistence layer.
- `app/jobs/` remains the canonical worker execution ledger. Data Lifecycle may enqueue canonical jobs only through the shared dispatcher.
- `app/settings/data_lifecycle_compat.py` is redirect-only compatibility. It must not render templates, mutate lifecycle data, or import retention execution services.

## URL Contract

Canonical URL:

`/platform-operations/data-lifecycle/`

Legacy `/settings/data-lifecycle/` endpoints remain temporary compatibility redirects. GET uses a normal redirect; mutation endpoints use method-preserving redirects so stale pages/bookmarks do not silently execute a second implementation.

## RBAC Contract

Canonical permissions are:

- `platform_operations.view_data_lifecycle`
- `platform_operations.manage_data_lifecycle`
- `platform_operations.export_data_lifecycle`

The ownership migration renames the former `settings.*_data_lifecycle` permission rows **in place** and changes their module to `operations`. Existing role-permission assignments therefore keep their permission IDs and access semantics. The migration also handles a defensive dual-row state without losing custom-role assignments.

## Workspace Contract

1. The page uses the shared KAORI Page Hero and Framed Workspace Tabs.
2. It does not own page-local tab geometry or hardcoded light-only tab surfaces.
3. Only registered archive adapters appear as managed domains. Roadmap/Planned Domain placeholders are not shown.
4. Retention Policies owns policy intent, exact preview, schedule intent, and manual archive requests.
5. Archive Storage owns shared archive-target posture and the archive-first safety boundary.
6. Archive History owns archive artifact, checksum, verification, cleanup, and download evidence. It is not a duplicate JobExecution registry.
7. Runtime state, retries, cancellation, worker readiness, and generic JobExecution details remain in Jobs & Executions.
8. Archive History pagination follows KAORI table standards with Title Case resource naming, visible `Rows`, and default 5 rows.
9. Dark mode is semantic-surface based. No `bg-white`, raw palette utility, raw hex, or page-local inline styling is accepted.

## Safety Invariants

- Cleanup never starts before the archive data and manifest checksums are verified.
- Selection remains frozen by immutable retention boundary and source IDs.
- Manual lifecycle execution uses `enqueue_canonical_job`; no direct Celery dispatch is owned by the page.
- Operational feedback and Activity Audit evidence are persisted for policy changes, execution requests, archive verification, and failures.
- Verified archive download remains separately permission-gated.
- Adding a future domain requires a registered retention adapter and explicit safety boundary before it can appear in the UI.

## Final Lock Enforcement

```bash
python scripts/verify_data_lifecycle_final_lock.py
python scripts/verify_platform_operations_final_lock.py
pytest -q tests/contracts/platform_operations/test_data_lifecycle_final_lock_contract.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
python scripts/verify_migration_graph.py
```
