# KAORI Platform Operations Final Lock v1.1 Audit — 2026-08-08

## Audit Result

The Jobs & Executions portion of Platform Operations was intentionally reopened after the v1 lock because the presentation was visually stable but several runtime semantics could mislead an operator. The information architecture remains unchanged.

## Findings Closed

### Active Work stale empty state

The five-second Active Work fragment poll previously existed only while at least one active row was rendered. If the page entered an empty state, the polling attributes disappeared and a later execution could not appear until manual refresh or page reload. v1.1 keeps the existing five-second poll alive in both populated and empty states.

### Unbounded historical attention

The v1 attention counter included all retained `failed` and `partially_succeeded` executions. A historical failure could therefore keep `Needs Attention` non-zero for the entire retention period. v1.1 separates active intervention (`retrying`, `cancel_requested`) from recent terminal attention (`failed`, `partially_succeeded`, `expired`) and bounds terminal attention to 24 hours.

### Registry evidence gap

The canonical model already stores worker task identity, scope, lifecycle timestamps, result references, structured summaries, and failure evidence, but the Registry exposed only row-level status and cancellation. v1.1 adds shared expandable `View Details` content below each Registry row. Raw execution payloads and internal deduplication fingerprints remain hidden.

### Registry metric ambiguity

The Registry displayed a filtered record count while a second strip displayed unfiltered global totals. The two scopes could be read as one filter result. v1.1 removes the duplicated global strip; Execution Overview remains the owner of global execution metrics.

### Queue demand without worker readiness

Queue Activity previously stated that it did not represent worker liveness. Operators could see queued work without knowing whether any worker consumed the queue. v1.1 reuses the existing Celery queue-health service and displays Online, Worker Missing, Offline, or Unknown readiness beside execution demand.

Topology inspection is executed once per Queue Activity render and shared across queue rows. Active/Registry fragment refreshes explicitly skip queue inspection to keep the five-second Active Work polling lightweight.

### Hero attention ambiguity

The hero used the label `Needs Attention` for Job Configuration-only attention while Execution Overview used the same label for execution attention. v1.1 renames the hero metric to `Operational Attention` and combines both bounded execution attention and configuration attention.

## Lock Decision

Platform Operations remains structurally locked. The Jobs & Executions v1.1 semantics are accepted when the dedicated final-lock verifier, generic UI lock, dark-mode verification, Python syntax verification, and Jobs contracts all pass.
