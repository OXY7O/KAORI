# KAORI Platform Operations Lock v1.1

Status: Locked refinement baseline
Date: 2026-08-08
Supersedes: Jobs & Executions interaction semantics in `KAORI_PLATFORM_OPERATIONS_LOCK_V1.md`

## Scope

Platform Operations v1 remains the visual and information-architecture baseline. v1.1 intentionally reopens only the Jobs & Executions operational semantics that were found to be incomplete during post-lock review.

The following structure remains frozen:

- Jobs & Executions
  - Executions
    - Execution Overview
    - Active Work
    - Registry
    - Queues
  - Job Configuration

No new top-level workspace, modal detail pattern, alternate scheduler, or page-local tab implementation is introduced.

## Jobs & Executions v1.1 Contract

1. **Active Work polling remains live in the empty state.** The Active Work fragment keeps its five-second HTMX refresh contract even when no execution is currently active, so a newly queued execution can appear without a page reload.
2. **Attention is bounded operational posture, not retention history.** `retrying` and `cancel_requested` are active attention. `failed`, `partially_succeeded`, and `expired` remain attention for 24 hours after terminal completion. Historical terminal failures older than that window stay searchable but do not keep the overview permanently degraded.
3. **Execution Registry statistics are filter-safe.** The Registry header owns the filtered record count. The duplicated global metric strip is removed because global execution metrics already belong to Execution Overview and could be mistaken for filtered statistics.
4. **Execution evidence expands below the Registry row.** `View Details` uses the shared KAORI expandable-row interaction. The operator view exposes canonical identity, ownership/scope, lifecycle, result summary/reference, and error evidence without rendering raw request payloads, deduplication keys, or parameter fingerprints.
5. **Queue Activity includes Celery worker readiness.** Queue rows combine canonical JobExecution demand with worker readiness from `app/common/celery_queue_health.py`.
6. **Celery inspection is bounded.** Queue Activity performs one topology inspection snapshot per render and reuses it across all queues. Active Work and Registry fragment refreshes skip queue topology inspection.
7. **Queue Activity supports explicit refresh.** The Queue fragment is independently HTMX-refreshable without replacing the surrounding Execution Workspace.
8. **Hero posture is domain-wide.** The hero metric is `Operational Attention`, combining current execution attention with Job Configuration attention so the top-level wording does not imply two unrelated meanings for `Needs Attention`.
9. **KAORI v1 visual standards remain frozen.** Title Case, shared violet/semantic tokens, shared pagination, shared loading/status primitives, no raw palette colors, no inline handlers, and responsive no-horizontal-table Registry behavior remain unchanged.

## Enforcement

The release gate continues to run:

```bash
python scripts/verify_platform_operations_final_lock.py
python scripts/verify_core_workspace_ui_lock.py
python scripts/verify_dark_mode_standard.py
python scripts/verify_python_syntax.py
pytest -q tests/contracts/jobs
```

The final-lock verifier now validates both the original v1 baseline and this v1.1 Jobs & Executions refinement. Future changes to these semantics require another explicit lock revision with matching documentation and contracts.
