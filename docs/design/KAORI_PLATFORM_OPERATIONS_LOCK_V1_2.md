# KAORI Platform Operations Lock v1.2

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Job Configuration presentation and initial-render behavior in `KAORI_PLATFORM_OPERATIONS_LOCK_V1_1.md`

## Scope

Platform Operations v1.1 remains the execution-semantics baseline. v1.2 reopens only the Jobs & Executions **Job Configuration** workspace for operational-feedback, rendering-performance, and copy-density refinements. The top-level information architecture remains unchanged.

## Job Configuration v1.2 Contract

1. **Background Inventory Sync does not open a progress toast.** Manual dispatch remains persisted through Activity Audit/Activity Center, while live progress stays in the Job Configuration execution activity and canonical Executions workspace. Immediate blocking/error feedback may still use the shared operational feedback contract.
2. **Inactive Queue Activity is not inspected.** A full-page Job Configuration request builds execution data without Celery Queue Activity topology inspection. Executions keeps its existing worker-readiness behavior.
3. **Policy Timeline uses a clear card surface.** Inventory, TLS, Analytics, and Forecast policy timelines use `bg-surface-card` with the shared KAORI border tokens.
4. **Report delivery-channel cards use a clear card surface.** Email, Telegram, Slack, and Webhook readiness cards use `bg-surface-card`; no raw white/dark palette utilities are introduced.
5. **Configuration copy stays concise.** Stale fallback and workspace helper copy are shortened without changing semantics. Registered-job descriptions for Inventory Sync, Report Schedule Dispatcher, and Analytics Data Refresh are compact.
6. **Planned Job Definitions is removed.** Job Configuration lists only registered/operational definitions; speculative future jobs do not occupy the production control surface.
7. **Existing v1.1 execution contracts remain frozen.** Empty-state Active Work polling, bounded attention, expandable Registry detail, worker readiness, filter-safe Registry counts, and Operational Attention remain unchanged.

## Enforcement

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/jobs
```
