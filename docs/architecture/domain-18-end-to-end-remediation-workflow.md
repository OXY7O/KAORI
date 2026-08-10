# Domain 18 — End-to-End Remediation Workflow Integration

> **Current release status (2026-08-10): Historical design reference.** The dormant `app/knowledge/remediation_workflow.py` orchestrator was removed from the release source because it had no runtime/test/entrypoint consumer. Intelligence remediation is held for the next controlled redesign; this document must not be read as an enabled current-release execution path.

## Purpose

Domain 18 connects the safety components from Domains 8–17 into one explicit remediation workflow without collapsing their authorization boundaries.

```text
Alert → Runbook match → Candidate → Review promotion → Decision
      → Approval → One-time authorization → Canonical job → Resolver worker
      → Dry-run → Token consumption → Mutation → Execution journal
```

## Production Changes

### Historical `app/knowledge/remediation_workflow.py`

The retired prototype provided three application-level entry points:

- `ingest_alert_for_review()` matches an alert and persists a non-executable candidate;
- `promote_reviewed_candidate()` performs explicit candidate-to-decision promotion;
- `approve_and_enqueue_decision()` performs approval when required, issues one authorization journal, and enqueues through the canonical job dispatcher.

The module deliberately does not import or call `dispatch_resolver_execution()`. Provider mutation stays worker-side.

### `app/resolver/tasks.py`

Adds the `execute_authorized_resolution` Celery task on the dedicated `resolver-execution` queue. The worker:

1. acquires a distributed lease;
2. loads the process-local resolver registry;
3. executes dry-run and authorized resolver dispatch;
4. completes orchestration on success;
5. classifies terminal and retryable failures;
6. preserves dead-letter and stale-lease recovery from Domain 11.

## Safety Properties

- alert ingestion cannot produce executable payloads;
- candidate promotion remains explicit;
- approval and execution permissions stay separate;
- authorization is issued before queue delivery;
- provider mutation occurs only in the resolver worker;
- execution uses the registry initialized for that worker process;
- execution remains idempotent through the journal and canonical job foundation;
- a worker must own the active lease before dispatch.

## Deployment

No migration is added. Apply after Domain 17, then restart web, Celery worker, and beat processes so all processes load the same resolver registry configuration.

Route the task explicitly:

```python
'app.resolver.tasks.execute_authorized_resolution': {
    'queue': 'resolver-execution',
}
```

Keep the queue unconsumed until non-production resolver policy and registry fingerprints have been validated.

## Historical Validation

The original Domain 18 test paths were retired together with the dormant application orchestrator. The current release must instead prove that the retired module is absent and that no unresolved runtime/import dependency remains:

```bash
python scripts/verify_module_reachability.py
python scripts/verify_import_cycles.py
python scripts/verify_architecture_boundaries.py
```

A future Intelligence remediation redesign must add new permanent contract and functional tests before any end-to-end mutation path is enabled again.

## Rollback

1. stop consumers of `resolver-execution`;
2. disable resolver deployment policies;
3. preserve pending/queued/running journals and Activity Audit evidence;
4. restore only an approved, tested remediation application contract and the matching resolver worker implementation;
5. restart web and workers.

No database downgrade is required.
