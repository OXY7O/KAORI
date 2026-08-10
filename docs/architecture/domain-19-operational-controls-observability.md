# Domain 19 — Operational Controls & Resolver Observability

> **Current release status (2026-08-10): Foundation retained; automated Intelligence remediation remains held.** Operational-control primitives may remain in use by controlled resolver paths, but this document does not imply that the retired Domain 18 application orchestrator is enabled.

## Purpose

Domain 19 adds fail-closed operational controls around the end-to-end remediation workflow. Resolver execution must stop when KAORI's global kill switch, cluster maintenance mode, concurrency limit, rate limit, or circuit breaker blocks the target.

## Controls

- Global kill switch: global control record only; defaults off.
- Cluster maintenance mode: blocks mutation for one cluster.
- Concurrency limit: defaults to one active execution per cluster.
- Rate limit: defaults to ten candidate execution journals per minute per cluster.
- Circuit breaker: opens after three consecutive failures for five minutes by default.
- Dead-letter requeue: explicit operator action with Activity Audit evidence.

## Execution ordering

`assert_execution_allowed()` runs before distributed lease acquisition and before provider dispatch. The worker never consumes an execution token while an operational control blocks the action.

## Observability

`resolver_metrics_snapshot()` exposes queued, running, retry-wait, dead-letter, and stale-running counts. Control changes, circuit opening, and dead-letter requeue actions create Activity Audit events.

## Deployment

Run the migration, create the global control record, keep the kill switch off only in non-production acceptance, and set per-cluster limits before enabling a deployment policy.

## Validation

Run functional and contract tests, architecture checks, and query the operational-control and execution-journal tables. Simulate maintenance mode, concurrency saturation, repeated failures, and dead-letter requeue.

## Rollback

Disable deployment policies and stop resolver workers before downgrade. Export operational controls, circuit state, dead-letter journals, and audit events. Downgrade to `20260723_resolver_registry`.
