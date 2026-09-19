# Domain 9 — Decision Persistence, Approval, and Execution Journal

## Purpose

Domain 9 persists the immutable decision contract introduced in Domain 8. It creates an auditable boundary between a recommendation, human authorization, and resolver dispatch. It does not implement autonomous remediation or provider-specific resolver actions.

## State model

A decision starts as `ready` when policy allows direct execution or `pending_approval` when explicit approval is required. Valid terminal or forward states are `approved`, `rejected`, `expired`, and `dispatched`. A rejected decision cannot be reopened. An expired decision cannot issue or consume a token.

## Persistence

`intelligence_decisions` stores the complete immutable snapshot, canonical evidence hash, inventory generation, alert fingerprint, policy result, workflow status, creator, and TTL. `intelligence_decision_approvals` stores one append-only approval or rejection outcome. `intelligence_execution_journal` stores authorization and dispatch lifecycle without storing the raw signed token.

## One-time execution authorization

The signed token remains short-lived. KAORI stores only the SHA-256 hash of the token nonce. A unique database constraint prevents nonce reuse across replicas. Consumption locks the journal row, verifies current evidence, changes the journal to `dispatched`, and changes the decision to `dispatched` in the same transaction.

## RBAC

The code-owned permissions are:

- `intelligence.decisions.view`
- `intelligence.decisions.create`
- `intelligence.decisions.approve`
- `intelligence.decisions.execute`

Viewer and Auditor receive read-only visibility. Operator may create decisions. Editor and Admin may create, approve, and execute decisions. Custom-role permission expansion also makes each decision action depend on `intelligence.decisions.view`. Route enforcement will be added when the UI workflow is introduced.

## Audit

Creation, approval, rejection, authorization issuance, and dispatch create `AuditEvent` records in the same database transaction. Raw execution tokens are never written to the database or Activity Audit metadata.

## Deployment

Apply the migration after `20260722_foundation_cleanup`:

```bash
flask db upgrade
```

Run focused tests and the migration suite before deployment.

## Rollback

Stop decision workflow writes, verify no resolver job depends on a Domain 9 journal row, then downgrade one revision:

```bash
flask db downgrade 20260722_foundation_cleanup
```

The downgrade removes decision, approval, and execution journal history. Export audit evidence first if rollback occurs after production use.
