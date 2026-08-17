# KAORI Platform Operations Lock v1.8

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: v1.7 as the Platform Operations ownership baseline

## Scope

v1.8 preserves all Jobs & Executions and Secret Reveal contracts from v1.7 and adds **Data Lifecycle** as a first-class Platform Operations workspace. The detailed Data Lifecycle contract is frozen by `KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1.md`.

## Platform Operations Information Architecture

```text
Platform Operations
├── Jobs & Executions
├── Data Lifecycle
└── Kubernetes Administration
```

## v1.8 Contract

1. Data Lifecycle is not a Settings-owned workspace.
2. Navigation, breadcrumbs, route namespace, template namespace, RBAC namespace, activity links, and integration-runtime links all resolve to Platform Operations ownership.
3. The shared retention engine stays under `app/platform_operations/data_lifecycle/retention`; the Platform Operations package owns HTTP/UI orchestration.
4. Legacy Settings routes are redirect-only compatibility and may not regain mutation/rendering logic.
5. Data Lifecycle uses shared Framed Workspace Tabs and the generic Platform Operations UI lock.
6. Archive History is archive evidence only; canonical worker execution evidence remains in Jobs & Executions.
7. No roadmap domain is shown before a registered adapter exists.
8. Existing Secret Reveal v1.7 natural-height and activation-tip contracts remain unchanged.

## Enforcement

```bash
python scripts/verify_data_lifecycle_final_lock.py
python scripts/verify_platform_operations_final_lock.py
pytest -q tests/contracts/platform_operations
pytest -q tests/contracts/jobs
pytest -q tests/contracts/kubernetes -k "secret and reveal"
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
```
